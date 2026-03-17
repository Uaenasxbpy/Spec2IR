#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FUNC_ID_RE = re.compile(r"^alg_\d{3}_[a-z0-9_]+$")


@dataclass
class Issue:
    level: str  # ERROR | WARNING | INFO
    code: str
    path: str
    message: str


class IRChecker:
    def __init__(self, root: Path):
        self.root = root
        self.issues: List[Issue] = []
        self.summary: Dict[str, Any] = {
            "root": str(root),
            "files_checked": 0,
            "functions_indexed": 0,
            "functions_files": 0,
            "errors": 0,
            "warnings": 0,
        }

    def error(self, code: str, path: Path | str, message: str) -> None:
        self.issues.append(Issue("ERROR", code, str(path), message))

    def warn(self, code: str, path: Path | str, message: str) -> None:
        self.issues.append(Issue("WARNING", code, str(path), message))

    def info(self, code: str, path: Path | str, message: str) -> None:
        self.issues.append(Issue("INFO", code, str(path), message))

    def load_json(self, path: Path) -> Optional[Any]:
        if not path.exists():
            self.error("FILE_MISSING", path, "文件不存在")
            return None
        if not path.is_file():
            self.error("NOT_A_FILE", path, "目标路径不是文件")
            return None
        try:
            self.summary["files_checked"] += 1
            return json.loads(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            self.error("ENCODING_ERROR", path, f"文件不是 UTF-8 编码: {exc}")
        except json.JSONDecodeError as exc:
            self.error("JSON_PARSE_ERROR", path, f"JSON 解析失败: {exc}")
        return None

    def require_object(self, obj: Any, path: Path | str, field: str = "<root>") -> Optional[Dict[str, Any]]:
        if not isinstance(obj, dict):
            self.error("TYPE_ERROR", path, f"{field} 应为 object")
            return None
        return obj

    def require_list(self, obj: Any, path: Path | str, field: str) -> Optional[List[Any]]:
        if not isinstance(obj, list):
            self.error("TYPE_ERROR", path, f"{field} 应为 array")
            return None
        return obj

    def require_string(self, obj: Dict[str, Any], key: str, path: Path | str, allow_empty: bool = False) -> Optional[str]:
        if key not in obj:
            self.error("FIELD_MISSING", path, f"缺少字段 {key}")
            return None
        val = obj[key]
        if not isinstance(val, str):
            self.error("TYPE_ERROR", path, f"字段 {key} 应为 string")
            return None
        if not allow_empty and val.strip() == "":
            self.warn("EMPTY_STRING", path, f"字段 {key} 为空字符串")
        return val

    def require_int(self, obj: Dict[str, Any], key: str, path: Path | str, minimum: Optional[int] = None) -> Optional[int]:
        if key not in obj:
            self.error("FIELD_MISSING", path, f"缺少字段 {key}")
            return None
        val = obj[key]
        if not isinstance(val, int):
            self.error("TYPE_ERROR", path, f"字段 {key} 应为 int")
            return None
        if minimum is not None and val < minimum:
            self.error("VALUE_ERROR", path, f"字段 {key} 不应小于 {minimum}")
        return val

    def check_document_info(self) -> None:
        path = self.root / "document_info.json"
        data = self.load_json(path)
        if data is None:
            return
        obj = self.require_object(data, path)
        if obj is None:
            return
        doc = obj.get("document_info")
        if not isinstance(doc, dict):
            self.error("FIELD_MISSING", path, "缺少 object 字段 document_info")
            return
        for key in ["standard", "full_title", "publisher", "publication_date", "core_algorithm"]:
            self.require_string(doc, key, path)
        pub = doc.get("publication_date")
        if isinstance(pub, str) and pub and not DATE_RE.match(pub):
            self.warn("DATE_FORMAT", path, "publication_date 建议使用 YYYY-MM-DD 格式")

    def check_parameter_sets(self) -> None:
        path = self.root / "parameter_sets.json"
        data = self.load_json(path)
        if data is None:
            return
        obj = self.require_object(data, path)
        if obj is None:
            return
        sets_ = self.require_list(obj.get("parameter_sets"), path, "parameter_sets")
        if sets_ is None:
            return
        if not sets_:
            self.warn("EMPTY_ARRAY", path, "parameter_sets 为空")
        names = set()
        for idx, item in enumerate(sets_):
            item_path = f"{path}#parameter_sets[{idx}]"
            pobj = self.require_object(item, item_path)
            if pobj is None:
                continue
            name = self.require_string(pobj, "set_name", item_path)
            if name:
                if name in names:
                    self.error("DUPLICATE_SET", item_path, f"重复的参数集名称: {name}")
                names.add(name)
            params = self.require_list(pobj.get("parameters"), item_path, "parameters")
            if params is None:
                continue
            if not params:
                self.warn("EMPTY_ARRAY", item_path, "parameters 为空")
            pnames = set()
            for pidx, param in enumerate(params):
                ppath = f"{item_path}.parameters[{pidx}]"
                pobj2 = self.require_object(param, ppath)
                if pobj2 is None:
                    continue
                pname = self.require_string(pobj2, "name", ppath)
                if pname:
                    if pname in pnames:
                        self.error("DUPLICATE_PARAM", ppath, f"重复的参数名: {pname}")
                    pnames.add(pname)
                if "value" not in pobj2:
                    self.error("FIELD_MISSING", ppath, "缺少字段 value")
                self.require_string(pobj2, "type", ppath)
                self.require_string(pobj2, "description", ppath, allow_empty=True)

    def check_function_index(self) -> Dict[str, Dict[str, Any]]:
        path = self.root / "function_index.json"
        result: Dict[str, Dict[str, Any]] = {}
        data = self.load_json(path)
        if data is None:
            return result
        obj = self.require_object(data, path)
        if obj is None:
            return result
        funcs = self.require_list(obj.get("functions"), path, "functions")
        if funcs is None:
            return result
        if not funcs:
            self.warn("EMPTY_ARRAY", path, "functions 为空")
        ids = set()
        files = set()
        for idx, item in enumerate(funcs):
            item_path = f"{path}#functions[{idx}]"
            fobj = self.require_object(item, item_path)
            if fobj is None:
                continue
            fid = self.require_string(fobj, "function_id", item_path)
            name = self.require_string(fobj, "name", item_path)
            label = self.require_string(fobj, "label", item_path)
            ps = self.require_int(fobj, "page_start", item_path, minimum=1)
            pe = self.require_int(fobj, "page_end", item_path, minimum=1)
            file_rel = self.require_string(fobj, "file", item_path)
            if fid:
                if fid in ids:
                    self.error("DUPLICATE_FUNCTION_ID", item_path, f"重复的 function_id: {fid}")
                ids.add(fid)
                if not FUNC_ID_RE.match(fid):
                    self.warn("FUNCTION_ID_FORMAT", item_path, f"function_id 不符合建议格式: {fid}")
            if file_rel:
                if file_rel in files:
                    self.error("DUPLICATE_FILE_PATH", item_path, f"重复的 file: {file_rel}")
                files.add(file_rel)
                if not file_rel.endswith(".json"):
                    self.warn("FILE_PATH_FORMAT", item_path, "file 建议以 .json 结尾")
            if isinstance(ps, int) and isinstance(pe, int) and ps > pe:
                self.error("PAGE_RANGE", item_path, "page_start 不能大于 page_end")
            if fid and file_rel:
                result[fid] = {
                    "name": name,
                    "label": label,
                    "page_start": ps,
                    "page_end": pe,
                    "file": file_rel,
                }
        self.summary["functions_indexed"] = len(result)
        return result

    def check_io_array(self, arr: Any, path: str, field: str) -> None:
        items = self.require_list(arr, path, field)
        if items is None:
            return
        for idx, item in enumerate(items):
            ipath = f"{path}.{field}[{idx}]"
            obj = self.require_object(item, ipath)
            if obj is None:
                continue
            self.require_string(obj, "name", ipath)
            self.require_string(obj, "type", ipath)
            self.require_string(obj, "description", ipath, allow_empty=True)

    # 检查 functions 目录下的函数文件，验证其内容与索引的一致性，并统计未索引或缺失的文件
    def check_single_function_files(self, index_map: Dict[str, Dict[str, Any]]) -> None:
        functions_dir = self.root / "functions"
        if not functions_dir.exists():
            self.error("DIR_MISSING", functions_dir, "缺少 functions 目录")
            return
        if not functions_dir.is_dir():
            self.error("NOT_A_DIR", functions_dir, "functions 不是目录")
            return

        json_files = sorted(functions_dir.glob("*.json"))
        self.summary["functions_files"] = len(json_files)
        indexed_files = set()

        for fid, meta in index_map.items():
            rel = meta["file"]
            indexed_files.add(f"functions/{rel}")
            # print(f"检查索引函数: {fid} -> {rel}")
            path = self.root / "functions" / rel
            # print(f"检查函数文件: {path}")
            data = self.load_json(path)
            if data is None:
                continue
            obj = self.require_object(data, path)
            if obj is None:
                continue

            sfid = self.require_string(obj, "function_id", path)
            sname = self.require_string(obj, "name", path)
            slabel = self.require_string(obj, "label", path)
            sps = self.require_int(obj, "page_start", path, minimum=1)
            spe = self.require_int(obj, "page_end", path, minimum=1)
            self.check_io_array(obj.get("inputs"), str(path), "inputs")
            self.check_io_array(obj.get("outputs"), str(path), "outputs")
            body = self.require_list(obj.get("body_raw"), str(path), "body_raw")
            if body is not None:
                if not body:
                    self.error("EMPTY_BODY", path, "body_raw 不能为空")
                else:
                    for idx, line in enumerate(body):
                        if not isinstance(line, str):
                            self.error("TYPE_ERROR", path, f"body_raw[{idx}] 应为 string")
                        elif line.strip() == "":
                            self.warn("EMPTY_STRING", path, f"body_raw[{idx}] 是空行")

            if isinstance(sps, int) and isinstance(spe, int) and sps > spe:
                self.error("PAGE_RANGE", path, "page_start 不能大于 page_end")

            if sfid and sfid != fid:
                self.error("INDEX_MISMATCH", path, f"function_id 与索引不一致: {sfid} != {fid}")
            if sname is not None and sname != meta["name"]:
                self.error("INDEX_MISMATCH", path, f"name 与索引不一致: {sname} != {meta['name']}")
            if slabel is not None and slabel != meta["label"]:
                self.error("INDEX_MISMATCH", path, f"label 与索引不一致: {slabel} != {meta['label']}")
            if sps is not None and sps != meta["page_start"]:
                self.warn("INDEX_MISMATCH", path, f"page_start 与索引不一致: {sps} != {meta['page_start']}")
            if spe is not None and spe != meta["page_end"]:
                self.warn("INDEX_MISMATCH", path, f"page_end 与索引不一致: {spe} != {meta['page_end']}")

            expected_name = Path(meta["file"]).name
            # print(f"预期文件名: {expected_name}")
            if path.name != expected_name:
                self.error("FILE_NAME_MISMATCH", path, f"文件名与索引 file 不一致: {path.name} != {expected_name}")
            if sfid and path.stem != sfid:
                self.warn("FILE_STEM_MISMATCH", path, f"文件名 stem 与 function_id 不一致: {path.stem} != {sfid}")

        # unindexed files
        actual_rel_files = {f"functions/{p.name}" for p in json_files}
        extra_files = sorted(actual_rel_files - indexed_files)
        for rel in extra_files:
            self.warn("UNINDEXED_FILE", self.root / rel, "该函数文件未在 function_index.json 中登记")

        missing_files = sorted(indexed_files - actual_rel_files)
        for rel in missing_files:
            self.error("INDEX_FILE_MISSING", self.root / rel, "索引中声明了该函数文件，但实际不存在")

    def run(self) -> Dict[str, Any]:
        if not self.root.exists():
            self.error("ROOT_MISSING", self.root, "spec_ir 根目录不存在")
            return self.report()
        if not self.root.is_dir():
            self.error("ROOT_NOT_DIR", self.root, "spec_ir 根路径不是目录")
            return self.report()

        self.check_document_info()
        self.check_parameter_sets()
        index_map = self.check_function_index()
        self.check_single_function_files(index_map)
        return self.report()

    def report(self) -> Dict[str, Any]:
        errors = sum(1 for i in self.issues if i.level == "ERROR")
        warnings = sum(1 for i in self.issues if i.level == "WARNING")
        self.summary["errors"] = errors
        self.summary["warnings"] = warnings
        return {
            "summary": self.summary,
            "issues": [asdict(i) for i in self.issues],
        }


def print_human_report(report: Dict[str, Any]) -> None:
    summary = report["summary"]
    print("=" * 72)
    print("SpecIR 检查结果")
    print("=" * 72)
    print(f"根目录              : {summary['root']}")
    print(f"已检查 JSON 文件数    : {summary['files_checked']}")
    print(f"索引中的函数数量      : {summary['functions_indexed']}")
    print(f"functions 目录文件数 : {summary['functions_files']}")
    print(f"错误数              : {summary['errors']}")
    print(f"警告数              : {summary['warnings']}")

    if not report["issues"]:
        print("\n未发现问题。")
        return

    print("\n问题明细:")
    for idx, issue in enumerate(report["issues"], start=1):
        print(f"{idx:03d}. [{issue['level']}] {issue['code']} :: {issue['path']}")
        print(f"     {issue['message']}")


def main() -> int:
    default_root = (Path(__file__).resolve().parent.parent / "spec_ir").resolve()
    parser = argparse.ArgumentParser(description="检查 SpecIR 目录结构、字段结构和一致性")
    parser.add_argument("--root", type=Path, default=default_root, help="spec_ir 根目录，默认是脚本同级上层的 assets/spec_ir")
    parser.add_argument("--json-report", type=Path, default=None, help="可选：将检查报告写入 JSON 文件")
    args = parser.parse_args()

    checker = IRChecker(args.root.resolve())
    report = checker.run()
    print_human_report(report)

    # 总是将报告写入到 check_result.txt
    script_dir = Path(__file__).resolve().parent
    result_file = script_dir / "check_result.txt"
    result_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入检查结果: {result_file}")

    if args.json_report is not None:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 JSON 报告: {args.json_report}")

    return 1 if report["summary"]["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
