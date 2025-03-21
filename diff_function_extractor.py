"""
DiffFunctionExtractor 模块

负责从GitHub仓库的提交中提取差异信息，包括改动的文件列表、变更前后的文件内容和详细的diff块信息。
"""

import os
import re
import logging
import json
from typing import Dict, List, Tuple, Any, Optional, Set
from pathlib import Path
import requests
import traceback
import sys

# 导入tree-sitter相关库，保留原有导入方式
try:
    from tree_sitter import Parser, Node, Tree
    from tree_sitter_language_pack import get_language, get_parser
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False
    raise ImportError(
        "必要的库未安装，请运行以下命令安装:\n"
        "pip install tree-sitter tree-sitter-language-pack"
    )

# 修复相对导入问题
from zast_extract.github_client import GitHubClient
from zast_extract.config import logger

class DiffFunctionExtractor:
    """
    从GitHub仓库的提交中提取差异信息
    
    该类可以：
    1. 拉取指定提交的所有改动文件列表和对应的diff
    2. 分析每个文件的变更前后版本和详细的diff块信息
    3. 处理文件重命名或移动的情况
    4. 将所有信息以结构化数据返回
    """
    
    # 支持的编程语言和对应的文件扩展名
    SUPPORTED_LANGUAGES = {
        'python': ['.py'],
        'javascript': ['.js'],
        'typescript': ['.ts', '.tsx'],
        'java': ['.java'],
        'go': ['.go'],
        'php': ['.php'],
        'ruby': ['.rb'],
        'c': ['.c', '.h'],
        'cpp': ['.cpp', '.hpp', '.cc', '.hh', '.cxx', '.hxx'],
        'rust': ['.rs'],
    }
    
    # 不同语言的函数/方法定义节点类型
    FUNCTION_NODE_TYPES = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'method_definition', 'arrow_function', 'function'],
        'typescript': ['function_declaration', 'method_definition', 'arrow_function', 'function'],
        'java': ['method_declaration', 'constructor_declaration'],
        'go': ['function_declaration', 'method_declaration'],
        'php': ['function_definition', 'method_declaration'],
        'ruby': ['method', 'singleton_method'],
        'c': ['function_definition'],
        'cpp': ['function_definition', 'constructor_declaration', 'destructor_declaration'],
        'rust': ['function_item'],
    }
    
    # 不同语言的匿名函数/闭包节点类型
    ANONYMOUS_FUNCTION_TYPES = {
        'python': ['lambda'],
        'javascript': ['arrow_function', 'function'],
        'typescript': ['arrow_function', 'function'],
        'java': ['lambda_expression'],
        'go': ['func_literal'],
        'rust': ['closure_expression'],
    }
    
    # 不同语言的类定义节点类型
    CLASS_NODE_TYPES = {
        'python': ['class_definition'],
        'javascript': ['class_declaration', 'class'],
        'typescript': ['class_declaration', 'class'],
        'java': ['class_declaration'],
        'go': ['type_declaration'],  # Go没有传统类，使用type和struct
        'php': ['class_declaration'],
        'ruby': ['class', 'module'],
        'c': [], # C没有类
        'cpp': ['class_specifier', 'struct_specifier'],
        'rust': ['impl_item'],
    }
    
    def __init__(self):
        """初始化DiffFunctionExtractor"""
        self.github_client = GitHubClient()
        self.parsers = {}
        
        # 初始化Tree-sitter解析器
        if TS_AVAILABLE:
            self._init_tree_sitter_parsers()
    
    def _init_tree_sitter_parsers(self):
        """初始化各个语言的Tree-sitter解析器"""
        for lang in self.SUPPORTED_LANGUAGES.keys():
            try:
                # 使用language_pack的get_parser函数直接获取配置好的解析器
                self.parsers[lang] = get_parser(lang)
                logger.debug(f"成功初始化 {lang} 解析器")
            except Exception as e:
                logger.warning(f"初始化 {lang} 解析器失败: {str(e)}")
    
    def extract_commit_diff(self, repo_url: str, commit_sha: str) -> Dict[str, Any]:
        """
        提取指定提交的差异信息
        
        Args:
            repo_url: GitHub仓库URL
            commit_sha: 提交的SHA值
            
        Returns:
            提交差异信息的字典
        """
        # 从URL提取仓库名称
        repo_name = self._extract_repo_name_from_url(repo_url)
        logger.info(f"正在分析仓库 {repo_name} 的提交 {commit_sha}")
        
        # 获取提交的diff文本
        diff_text = self.github_client.get_commit_diff(repo_name, commit_sha)
        if not diff_text:
            logger.error(f"无法获取提交的diff文本")
            return {
                "repo_name": repo_name,
                "commit_sha": commit_sha,
                "files": [],
                "error": "无法获取提交的diff文本"
            }
        
        # 解析diff文本，提取文件信息
        files_data = self._parse_diff_text(diff_text)
        
        # 为每个文件生成AST并分析改动的函数
        for file_data in files_data:
            # 生成AST
            old_ast_result = self._generate_ast(file_data['old_path'], file_data['complete_old_content'])
            new_ast_result = self._generate_ast(file_data['new_path'], file_data['complete_new_content'])
            
            file_data['old_ast'] = old_ast_result
            file_data['new_ast'] = new_ast_result
            
            # 分析改动的函数
            if old_ast_result['success'] and new_ast_result['success']:
                modified_functions = self._analyze_modified_functions(
                    file_data['diff_blocks'], 
                    old_ast_result, 
                    new_ast_result,
                    file_data['old_path']
                )
                file_data['modified_functions'] = modified_functions
            else:
                logger.warning(f"无法分析函数改动: AST解析失败 - {file_data['new_path']}")
                file_data['modified_functions'] = []
        
        # 返回结构化数据
        return {
            "repo_name": repo_name,
            "commit_sha": commit_sha,
            "files": files_data
        }
    
    def _analyze_modified_functions(self, diff_blocks: List[Dict[str, Any]], 
                                  old_ast_result: Dict[str, Any], 
                                  new_ast_result: Dict[str, Any],
                                  file_path: str) -> List[Dict[str, Any]]:
        """
        分析差异块中修改的函数
        
        Args:
            diff_blocks: 差异块列表
            old_ast_result: 旧文件AST解析结果
            new_ast_result: 新文件AST解析结果
            file_path: 文件路径
            
        Returns:
            修改的函数信息列表
        """
        modified_functions = []
        
        # 获取旧版本和新版本的AST
        old_ast = old_ast_result.get('ast', {})
        new_ast = new_ast_result.get('ast', {})
        
        # 提取旧版本和新版本的所有函数节点
        old_function_nodes = self._extract_function_nodes(old_ast, file_path, old_ast_result.get('language', ''))
        new_function_nodes = self._extract_function_nodes(new_ast, file_path, new_ast_result.get('language', ''))
        
        # 建立新函数ID到旧函数的映射
        new_to_old_map = self._find_matching_functions(old_function_nodes, new_function_nodes)
        
        # 分析每个差异块
        for block in diff_blocks:
            # 对于每个差异块，检查它是否修改了任何函数
            old_start, old_count = block['old_start'], block['old_count']
            new_start, new_count = block['new_start'], block['new_count']
            
            # 旧文件中被修改行的范围
            old_modified_range = range(old_start, old_start + old_count)
            # 新文件中被修改行的范围
            new_modified_range = range(new_start, new_start + new_count)
            
            # 检查是否有函数被修改
            found_functions = False
            
            # 检查新文件中的函数
            for func_node in new_function_nodes:
                # 获取函数在新文件中的行范围
                func_start, func_end = func_node['start_line'], func_node['end_line']
                func_range = range(func_start, func_end + 1)
                
                # 检查函数是否与修改范围有交集
                if any(line in func_range for line in new_modified_range):
                    # 函数被修改
                    found_functions = True
                    
                    # 获取对应的旧函数
                    old_func_node = new_to_old_map.get(func_node['id'])
                    
                    # 创建函数信息
                    func_info = {
                        'name': func_node['name'],
                        'start_line': func_start,
                        'end_line': func_end,
                        'class_name': func_node.get('class_name', ''),
                        'file_path': file_path,
                        'type': func_node.get('type', 'unknown')
                    }
                    
                    # 对于匿名函数或promise处理函数，增加更多元数据以帮助识别
                    if func_node['name'].startswith('anonymous_') or '_handler' in func_node['name']:
                        # 提取匿名函数或处理函数的第一行文本，便于识别
                        func_info['function_snippet'] = func_node.get('text', '').split('\n')[0][:100] if func_node.get('text') else ''
                        
                        # 标记promise处理函数
                        if '_handler' in func_node['name']:
                            func_info['is_promise_handler'] = True
                            func_info['handler_type'] = func_node['name'].split('_')[0]  # then, catch, finally
                    
                    # 如果找到了对应的旧函数，记录其位置
                    if old_func_node:
                        func_info['old_start_line'] = old_func_node['start_line']
                        func_info['old_end_line'] = old_func_node['end_line']
                        # 对于匿名函数/promise处理函数，记录旧版本的代码片段
                        if old_func_node['name'].startswith('anonymous_') or '_handler' in old_func_node['name']:
                            func_info['old_function_snippet'] = old_func_node.get('text', '').split('\n')[0][:100] if old_func_node.get('text') else ''
                    
                    modified_functions.append(func_info)
            
            # 如果没有找到被修改的函数，则尝试检查是否附近有匿名函数或promise handler
            if not found_functions:
                # 检查附近是否有匿名函数或promise处理函数
                nearby_functions = []
                for func_node in new_function_nodes:
                    # 检查函数是否在修改范围附近（前后5行内）
                    func_range = range(func_node['start_line'] - 5, func_node['end_line'] + 5)
                    if any(line in func_range for line in new_modified_range):
                        # 可能是附近的匿名函数被修改
                        if func_node['name'].startswith('anonymous_') or '_handler' in func_node['name']:
                            nearby_functions.append(func_node)
                
                # 如果找到了附近的匿名函数或promise处理函数，将其视为可能被修改的函数
                if nearby_functions:
                    for func_node in nearby_functions:
                        old_func_node = new_to_old_map.get(func_node['id'])
                        func_info = {
                            'name': func_node['name'],
                            'start_line': func_node['start_line'],
                            'end_line': func_node['end_line'],
                            'class_name': func_node.get('class_name', ''),
                            'file_path': file_path,
                            'type': func_node.get('type', 'unknown'),
                            'is_nearby_function': True  # 标记为附近的函数，而非精确匹配
                        }
                        
                        if old_func_node:
                            func_info['old_start_line'] = old_func_node['start_line']
                            func_info['old_end_line'] = old_func_node['end_line']
                        
                        modified_functions.append(func_info)
                        found_functions = True
            
            # 如果没有找到被修改的函数，则标记为非函数区域的改动
            if not found_functions and (old_count > 0 or new_count > 0):
                logger.info(f"文件 {file_path} 的改动不在任何函数内 (行 {old_start}-{old_start + old_count - 1} -> {new_start}-{new_start + new_count - 1})")
                
                # 添加非函数区域改动信息
                non_func_info = {
                    'name': 'non_function_area',
                    'start_line': new_start,
                    'end_line': new_start + new_count - 1 if new_count > 0 else new_start,
                    'old_start_line': old_start,
                    'old_end_line': old_start + old_count - 1 if old_count > 0 else old_start,
                    'is_outside_function': True,
                    'file_path': file_path
                }
                modified_functions.append(non_func_info)
        
        return modified_functions
    
    def _find_matching_functions(self, old_ast_nodes: List[Dict[str, Any]], 
                                new_ast_nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        查找新旧AST中匹配的函数
        
        Args:
            old_ast_nodes: 旧AST中的函数节点列表
            new_ast_nodes: 新AST中的函数节点列表
            
        Returns:
            新函数ID到旧函数的映射
        """
        # 创建函数名到节点的映射
        old_func_map = {}
        for node in old_ast_nodes:
            # 为普通函数使用 "类名.函数名" 作为键
            key = f"{node.get('class_name', '')}.{node['name']}" if node.get('class_name') else node['name']
            old_func_map[key] = node
            
            # 对于匿名函数，添加基于位置的匹配策略
            if node['name'].startswith('anonymous_') or '_handler' in node['name']:
                # 匿名函数的代码位置可能变化，但结构可能相似，尝试存储更多信息
                line_key = f"line_{node['start_line']}"
                old_func_map[line_key] = node
                
                # 适用于promise处理函数：基于行号的approximate matching
                if '_handler' in node['name']:
                    handler_name = node['name'].split('_')[0]  # 'then', 'catch', 'finally'
                    handler_key = f"{handler_name}_handler"
                    old_func_map[handler_key] = node
        
        # 建立函数ID映射
        new_to_old_map = {}
        for node in new_ast_nodes:
            # 常规匹配：基于函数名和类名
            key = f"{node.get('class_name', '')}.{node['name']}" if node.get('class_name') else node['name']
            if key in old_func_map:
                new_to_old_map[node['id']] = old_func_map[key]
                continue
                
            # 对于匿名函数，尝试基于位置匹配
            if node['name'].startswith('anonymous_') or '_handler' in node['name']:
                # 精确位置匹配
                line_key = f"line_{node['start_line']}"
                if line_key in old_func_map:
                    new_to_old_map[node['id']] = old_func_map[line_key]
                    continue
                
                # 对于promise handlers，按名称匹配
                if '_handler' in node['name']:
                    handler_name = node['name'].split('_')[0]  # 'then', 'catch', 'finally'
                    handler_key = f"{handler_name}_handler"
                    if handler_key in old_func_map:
                        new_to_old_map[node['id']] = old_func_map[handler_key]
                        continue
                
                # 如果匿名函数位置变化不大，尝试匹配附近的函数
                for i in range(-3, 4):  # 检查前后3行
                    alternate_line_key = f"line_{node['start_line'] + i}"
                    if alternate_line_key in old_func_map:
                        new_to_old_map[node['id']] = old_func_map[alternate_line_key]
                        break
        
        return new_to_old_map
    
    def _extract_function_nodes(self, ast_node: Dict[str, Any], file_path: str, language: str) -> List[Dict[str, Any]]:
        """
        从AST中提取所有函数节点
        
        Args:
            ast_node: AST节点字典
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            函数节点列表
        """
        if not ast_node:
            return []
        
        function_nodes = []
        
        # 获取该语言的函数节点类型和匿名函数类型
        function_types = self.FUNCTION_NODE_TYPES.get(language, [])
        anonymous_types = self.ANONYMOUS_FUNCTION_TYPES.get(language, [])
        class_types = self.CLASS_NODE_TYPES.get(language, [])
        
        # 递归函数，用于遍历AST
        def extract_nodes_recursive(node, parent_class=None):
            nonlocal function_nodes
            
            if not node or not isinstance(node, dict):
                return
            
            current_class = parent_class
            
            # 检查是否是类定义节点
            is_class = node['type'] in class_types
            if is_class:
                # 尝试提取类名
                class_name = self._extract_node_name(node, language)
                old_class = current_class
                current_class = class_name
            
            # 检查是否是函数定义节点
            is_function = node['type'] in function_types
            is_anonymous = node['type'] in anonymous_types
            
            # 针对JavaScript/TypeScript的promise链增强检测
            is_promise_handler = False
            if language in ['javascript', 'typescript']:
                # 检查是否是类似.then()或.catch()的回调函数
                if node['type'] in ['arrow_function', 'function']:
                    parent = node.get('parent', {})
                    if isinstance(parent, dict):
                        parent_type = parent.get('type', '')
                        # 检查父节点是否是函数调用，例如catch(...)
                        if parent_type == 'call_expression':
                            grandparent = parent.get('parent', {})
                            if isinstance(grandparent, dict):
                                # 检查调用对象是否是成员表达式，如obj.then或promise.catch
                                grandparent_type = grandparent.get('type', '')
                                if grandparent_type == 'member_expression':
                                    # 尝试获取方法名
                                    for child in grandparent.get('children', []):
                                        if child.get('type') == 'property_identifier':
                                            method_name = child.get('text', '')
                                            if method_name in ['then', 'catch', 'finally']:
                                                is_promise_handler = True
                                                # 为promise处理函数生成更有意义的名称
                                                func_name = f"{method_name}_handler"
            
            if is_function or is_anonymous or is_promise_handler:
                # 提取函数名
                func_name = self._extract_node_name(node, language)
                
                # 处理匿名函数
                if not func_name or func_name.startswith('unnamed_'):
                    if is_promise_handler:
                        # 使用之前识别的promise方法名
                        pass  # func_name已经在上面设置了
                    else:
                        # 为其他匿名函数生成唯一标识符
                        func_name = f"anonymous_{node['start_point']['row']}_{node['start_point']['column']}"
                
                # 添加到结果列表
                function_info = {
                    'type': node['type'],
                    'name': func_name,
                    'class_name': current_class,
                    'start_line': node['start_point']['row'],
                    'end_line': node['end_point']['row'],
                    'start_col': node['start_point']['column'],
                    'end_col': node['end_point']['column'],
                    'node': node,
                    'id': f"{file_path}:{node['start_point']['row']}:{node['start_point']['column']}"
                }
                function_nodes.append(function_info)
            
            # 递归处理子节点
            for child in node.get('children', []):
                # 设置子节点的父节点引用，用于维护父子关系
                if isinstance(child, dict):
                    child['parent'] = node
                extract_nodes_recursive(child, current_class)
            
            # 恢复类环境
            if is_class:
                current_class = parent_class
        
        # 从AST根节点开始递归提取
        extract_nodes_recursive(ast_node)
        
        return function_nodes
    
    def _extract_node_name(self, node: Dict[str, Any], language: str) -> str:
        """
        尝试从节点中提取名称
        
        Args:
            node: AST节点
            language: 编程语言
            
        Returns:
            节点名称
        """
        # 不同语言的名称提取策略
        if language == 'python':
            # Python函数定义：通常有一个名为'identifier'的子节点
            for child in node.get('children', []):
                if child['type'] == 'identifier':
                    return child['text']
        
        elif language in ['javascript', 'typescript']:
            # JS/TS函数：查找identifier子节点
            for child in node.get('children', []):
                if child['type'] == 'identifier':
                    return child['text']
                
        elif language in ['java', 'go', 'c', 'cpp']:
            # 很多语言的函数名通常是identifier节点
            for child in node.get('children', []):
                if child['type'] == 'identifier' or child['type'] == 'field_identifier':
                    return child['text']
        
        # 无法确定名称时，尝试使用节点类型作为标识
        return f"unnamed_{node['type']}"
    
    def _find_nodes_covering_lines(self, function_nodes: List[Dict[str, Any]], lines: Set[int]) -> List[Dict[str, Any]]:
        """
        查找覆盖指定行号的函数节点
        
        Args:
            function_nodes: 函数节点列表
            lines: 要查找的行号集合
            
        Returns:
            覆盖这些行的函数节点列表
        """
        if not lines:
            return []
        
        covering_nodes = []
        
        for func_node in function_nodes:
            # 检查函数是否覆盖任何一行
            start_line = func_node['start_line']
            end_line = func_node['end_line']
            
            # 检查是否有交集
            if any(start_line <= line <= end_line for line in lines):
                covering_nodes.append(func_node)
        
        return covering_nodes
    
    def _get_language_by_extension(self, file_path: str) -> Optional[str]:
        """
        根据文件扩展名确定编程语言
        
        Args:
            file_path: 文件路径
            
        Returns:
            对应的编程语言名称，如无法确定则返回None
        """
        if not file_path:
            return None
            
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        for lang, extensions in self.SUPPORTED_LANGUAGES.items():
            if ext in extensions:
                return lang
        
        return None
    
    def _preprocess_code(self, code: str, language: str) -> str:
        """
        预处理代码以提高解析成功率
        
        Args:
            code: 源代码
            language: 编程语言
            
        Returns:
            预处理后的代码
        """
        if not code.strip():
            return code
            
        # Go语言特殊处理：确保有包声明
        if language == 'go' and 'package ' not in code:
            code = "package main\n\n" + code
            
        # 修复不平衡的括号
        if language in ['go', 'java', 'javascript', 'typescript', 'c', 'cpp']:
            # 简单检查括号是否平衡
            brackets = {'(': ')', '{': '}', '[': ']'}
            stack = []
            
            for char in code:
                if char in brackets.keys():
                    stack.append(char)
                elif char in brackets.values():
                    if not stack or brackets[stack.pop()] != char:
                        # 不平衡，但我们不进行修复，只记录
                        logger.debug(f"检测到不平衡的括号，可能会影响AST解析")
                        break
            
        return code
    
    def _generate_ast(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        为文件内容生成AST
        
        Args:
            file_path: 文件路径
            content: 文件内容
            
        Returns:
            包含AST信息的字典或错误信息
        """
        result = {
            "success": False,
            "language": None,
            "error": None,
            "ast": None,
            "fallback_used": False
        }
        
        # 确定编程语言
        language = self._get_language_by_extension(file_path)
        result["language"] = language
        
        if not language or language not in self.parsers:
            result["error"] = f"不支持的语言或文件类型: {file_path}"
            return result
            
        if not TS_AVAILABLE:
            result["error"] = "Tree-sitter库不可用"
            return result
            
        try:
            # 预处理代码
            processed_code = self._preprocess_code(content, language)
            
            # 解析代码生成AST
            parser = self.parsers[language]
            tree = parser.parse(bytes(processed_code, 'utf8'))
            
            # 成功解析，将root_node转换为包含父子关系引用的字典结构
            result["success"] = True
            result["ast"] = self._convert_tree_to_dict(tree.root_node, None)
            
            return result
        except Exception as e:
            # 记录错误并尝试备选方案
            logger.warning(f"AST解析文件 {file_path} 失败: {str(e)}")
            result["error"] = str(e)
            
            # 尝试简单的备选方案：基于文本的扫描
            try:
                fallback_result = self._fallback_parse(content, language)
                result["fallback_used"] = True
                result["ast"] = fallback_result
                result["success"] = True
            except Exception as fallback_e:
                result["error"] += f"; 备选方案也失败: {str(fallback_e)}"
                
            return result
    
    def _convert_tree_to_dict(self, node: Node, parent=None) -> Dict[str, Any]:
        """
        将Tree-sitter节点转换为可序列化的字典
        
        Args:
            node: Tree-sitter节点
            parent: 父节点的字典引用（用于维护父子关系）
            
        Returns:
            表示节点及其子节点的字典
        """
        result = {
            "type": node.type,
            "text": node.text.decode('utf8') if hasattr(node, 'text') else "",
            "start_point": {"row": node.start_point[0], "column": node.start_point[1]},
            "end_point": {"row": node.end_point[0], "column": node.end_point[1]},
            "children": []
        }
        
        # 设置父节点引用（不会被序列化，仅用于在内存中保持引用关系）
        if parent is not None:
            result["parent"] = parent
        
        for child in node.children:
            # 传递当前节点作为子节点的父节点
            child_dict = self._convert_tree_to_dict(child, result)
            result["children"].append(child_dict)
            
        return result
    
    def _fallback_parse(self, content: str, language: str) -> Dict[str, Any]:
        """
        在AST解析失败时使用的备选解析方法
        
        Args:
            content: 源代码
            language: 编程语言
            
        Returns:
            模拟的AST结构
        """
        # 创建虚拟的AST结构
        lines = content.split('\n')
        
        # 创建一个虚拟节点作为根节点
        root = {
            "type": "virtual_root",
            "text": content,
            "start_point": {"row": 0, "column": 0},
            "end_point": {"row": len(lines), "column": len(lines[-1]) if lines else 0},
            "children": []
        }
        
        # 用简单的启发式方法找出函数或方法定义
        function_pattern = None
        if language == 'python':
            function_pattern = r'^\s*def\s+(\w+)\s*\(.*\):'
        elif language in ['javascript', 'typescript']:
            function_pattern = r'(function\s+(\w+)\s*\(.*\)|const\s+(\w+)\s*=\s*(?:function|\(.*\)\s*=>))'
        elif language == 'go':
            function_pattern = r'^\s*func\s+(\w+|\(\s*\w+\s+[*]?\w+\s*\)\s+\w+)\s*\(.*\)'
        elif language == 'java':
            function_pattern = r'^\s*(public|private|protected)?\s*(static)?\s*\w+\s+(\w+)\s*\(.*\)'
        
        # 如果有适用的模式，尝试找出函数
        if function_pattern:
            current_func = None
            func_start = 0
            
            for i, line in enumerate(lines):
                match = re.search(function_pattern, line)
                
                # 如果找到新函数的开始
                if match:
                    # 如果有正在处理的函数，添加到子节点
                    if current_func:
                        func_text = '\n'.join(lines[func_start:i])
                        func_node = {
                            "type": "function",
                            "name": current_func,
                            "text": func_text,
                            "start_point": {"row": func_start, "column": 0},
                            "end_point": {"row": i-1, "column": len(lines[i-1]) if i > 0 else 0},
                            "children": []
                        }
                        root["children"].append(func_node)
                    
                    # 开始处理新函数
                    current_func = match.group(1) if match.group(1) else "anonymous_function"
                    func_start = i
            
            # 处理最后一个函数
            if current_func:
                func_text = '\n'.join(lines[func_start:])
                func_node = {
                    "type": "function",
                    "name": current_func,
                    "text": func_text,
                    "start_point": {"row": func_start, "column": 0},
                    "end_point": {"row": len(lines)-1, "column": len(lines[-1]) if lines else 0},
                    "children": []
                }
                root["children"].append(func_node)
        
        # 如果无法识别函数，将整个内容作为一个"虚拟函数"返回
        if not root["children"]:
            virtual_func = {
                "type": "virtual_function",
                "name": "entire_file",
                "text": content,
                "start_point": {"row": 0, "column": 0},
                "end_point": {"row": len(lines)-1, "column": len(lines[-1]) if lines else 0},
                "children": []
            }
            root["children"].append(virtual_func)
        
        return root
    
    def _extract_repo_name_from_url(self, repo_url: str) -> str:
        """
        从GitHub仓库URL中提取仓库名称（格式：owner/repo）
        
        Args:
            repo_url: GitHub仓库URL
            
        Returns:
            仓库名称（格式：owner/repo）
        """
        if not repo_url:
            return ""
            
        # 处理不同格式的GitHub URL
        # 例如：https://github.com/owner/repo
        # 或：git@github.com:owner/repo.git
        try:
            if "github.com" in repo_url:
                if repo_url.startswith("http"):
                    # HTTP(S) URL格式
                    parts = repo_url.strip('/').split('/')
                    if len(parts) >= 4 and parts[2] == "github.com":
                        owner = parts[3]
                        repo = parts[4].replace('.git', '')
                        return f"{owner}/{repo}"
                elif "git@github.com:" in repo_url:
                    # SSH URL格式
                    parts = repo_url.split(':')[1].split('/')
                    owner = parts[0]
                    repo = parts[1].replace('.git', '')
                    return f"{owner}/{repo}"
            
            # 如果无法解析，返回空字符串
            logger.warning(f"无法从URL中提取仓库名称: {repo_url}")
            return ""
        except Exception as e:
            logger.warning(f"解析仓库URL时出错: {str(e)}")
            return ""
    
    def direct_get_commit_diff(self, repo_url: str, commit_sha: str) -> str:
        """
        直接从GitHub获取commit diff内容，而不通过GitHub API
        
        Args:
            repo_url: GitHub仓库URL
            commit_sha: 提交SHA
            
        Returns:
            提交的diff内容
        """
        # 构建diff URL
        repo_name = self._extract_repo_name_from_url(repo_url)
        diff_url = f"https://github.com/{repo_name}/commit/{commit_sha}.diff"
        
        try:
            import requests
            response = requests.get(diff_url, timeout=10)
            if response.status_code == 200:
                logger.info(f"成功从 {diff_url} 获取diff内容")
                return response.text
            else:
                logger.error(f"获取diff失败: HTTP状态码 {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"获取diff超时: {diff_url}")
            return None
        except Exception as e:
            logger.error(f"获取diff异常: {str(e)}")
            return None
    
    def _parse_diff_text(self, diff_text: str) -> List[Dict[str, Any]]:
        """
        解析diff文本，提取文件信息
        
        Args:
            diff_text: 完整的diff文本
            
        Returns:
            文件信息字典的列表
        """
        files_data = []
        current_file = None
        
        # 使用正则表达式分割diff文本为文件块
        file_pattern = r'diff --git a/(.*?) b/(.*?)\n'
        file_blocks = re.split(file_pattern, diff_text)
        
        # 第一个元素是空字符串，之后每三个元素为一组(匹配文本前的内容，第一个捕获组，第二个捕获组)
        for i in range(1, len(file_blocks), 3):
            if i+2 >= len(file_blocks):
                break
                
            old_path = file_blocks[i]
            new_path = file_blocks[i+1]
            content = file_blocks[i+2]
            
            # 确定文件变更类型
            change_type = "modified"
            if "new file mode" in content:
                change_type = "added"
            elif "deleted file mode" in content:
                change_type = "deleted"
            elif new_path != old_path:
                change_type = "renamed"
            
            # 解析文件内容和diff块
            old_content, new_content = self._extract_file_content(content)
            diff_blocks = self._parse_diff_blocks(content)
            
            # 尝试获取完整的文件内容
            try:
                repo_name = self._extract_repo_name_from_url("") if hasattr(self, '_extract_repo_name_from_url') else ""
                complete_old_content = self.github_client.get_file_content(repo_name, old_path, ref="HEAD~1") if repo_name else old_content
                complete_new_content = self.github_client.get_file_content(repo_name, new_path, ref="HEAD") if repo_name else new_content
            except Exception as e:
                logger.warning(f"无法获取完整文件内容: {str(e)}")
                complete_old_content = old_content
                complete_new_content = new_content
            
            file_data = {
                "old_path": old_path,
                "new_path": new_path,
                "change_type": change_type,
                "old_content": old_content,
                "new_content": new_content,
                "complete_old_content": complete_old_content,
                "complete_new_content": complete_new_content,
                "diff_blocks": diff_blocks
            }
            
            files_data.append(file_data)
        
        return files_data
    
    def _extract_file_content(self, diff_content: str) -> Tuple[str, str]:
        """
        从diff内容中提取变更前后的文件内容
        
        Args:
            diff_content: 文件的diff内容
            
        Returns:
            (变更前的文件内容, 变更后的文件内容)
        """
        lines = diff_content.split('\n')
        
        old_lines = []
        new_lines = []
        
        # 跳过diff头部信息
        i = 0
        while i < len(lines) and not lines[i].startswith('@@'):
            i += 1
        
        # 处理diff内容
        current_line = i
        while current_line < len(lines):
            line = lines[current_line]
            
            # 跳过hunk头部
            if line.startswith('@@'):
                current_line += 1
                continue
                
            # 添加变更行和上下文行
            if line.startswith('-'):
                old_lines.append(line[1:])
            elif line.startswith('+'):
                new_lines.append(line[1:])
            elif line.startswith(' '):
                old_lines.append(line[1:])
                new_lines.append(line[1:])
            
            current_line += 1
        
        return '\n'.join(old_lines), '\n'.join(new_lines)
    
    def _parse_diff_blocks(self, diff_content: str) -> List[Dict[str, Any]]:
        """
        解析diff块信息
        
        Args:
            diff_content: 文件的diff内容
            
        Returns:
            diff块信息的列表
        """
        lines = diff_content.split('\n')
        diff_blocks = []
        
        current_block = None
        old_line_num = 0
        new_line_num = 0
        
        for line in lines:
            # 处理hunk头部，例如: @@ -132,7 +132,7 @@ class Routes extends React.Component {
            if line.startswith('@@'):
                if current_block:
                    diff_blocks.append(current_block)
                
                # 解析hunk头部获取起始行号
                hunk_header = re.search(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
                if hunk_header:
                    old_start = int(hunk_header.group(1))
                    new_start = int(hunk_header.group(2))
                    
                    current_block = {
                        "old_start": old_start,
                        "new_start": new_start,
                        "old_count": 0,
                        "new_count": 0,
                        "lines": []
                    }
                    
                    # 提取函数/类上下文信息（如果存在）
                    context_match = re.search(r'@@ .+ @@ (.+)', line)
                    if context_match and context_match.group(1):
                        context = context_match.group(1).strip()
                        current_block["context"] = context
                        
                        # 尝试识别这是类定义还是函数定义
                        if re.search(r'class\s+\w+', context):
                            current_block["context_type"] = "class"
                            # 尝试提取类名
                            class_match = re.search(r'class\s+(\w+)', context)
                            if class_match:
                                current_block["class_name"] = class_match.group(1)
                        elif re.search(r'(function|def)\s+\w+', context):
                            current_block["context_type"] = "function"
                            # 尝试提取函数名
                            func_match = re.search(r'(?:function|def)\s+(\w+)', context)
                            if func_match:
                                current_block["function_name"] = func_match.group(1)
                        else:
                            # test by pengfei default is function
                            current_block["context_type"] = "function"
                    
                    old_line_num = old_start
                    new_line_num = new_start
                continue
                
            # 确保我们已经有一个当前块
            if not current_block:
                continue
                
            # 处理变更行
            if line.startswith('-'):
                current_block["lines"].append({
                    "type": "delete",
                    "old_line": old_line_num,
                    "content": line[1:]
                })
                old_line_num += 1
                current_block["old_count"] += 1
            elif line.startswith('+'):
                current_block["lines"].append({
                    "type": "add",
                    "new_line": new_line_num,
                    "content": line[1:]
                })
                new_line_num += 1
                current_block["new_count"] += 1
            elif line.startswith(' '):
                current_block["lines"].append({
                    "type": "context",
                    "old_line": old_line_num,
                    "new_line": new_line_num,
                    "content": line[1:]
                })
                old_line_num += 1
                new_line_num += 1
        
        # 添加最后一个块
        if current_block:
            diff_blocks.append(current_block)
            
        return diff_blocks
    
    def _format_output(self, diff_data: Dict[str, Any]) -> str:
        """
        格式化输出diff数据
        
        Args:
            diff_data: diff数据字典
            
        Returns:
            格式化的字符串
        """
        result = json.dumps(diff_data, ensure_ascii=False, indent=2)
        return result
    
    def extract_changed_functions_from_diff(self, diff_text: str, repo_url: str = None, commit_sha: str = None) -> List[Dict[str, Any]]:
        """
        直接从diff文本中提取变更的函数或类
        
        此方法通过解析diff的hunk头部来识别变更的函数或类，
        然后使用Tree-sitter解析相关代码段获取完整的函数或类定义。
        
        Args:
            diff_text: 完整的diff文本
            repo_url: GitHub仓库URL（可选，用于获取完整文件内容）
            commit_sha: 提交SHA（可选，用于获取完整文件内容）
            
        Returns:
            变更函数或类的列表
        """
        # 解析diff文本，提取文件信息
        files_data = self._parse_diff_text(diff_text)
        changed_functions = []
        
        # 如果提供了repo_url和commit_sha，尝试获取完整的文件内容
        if repo_url and commit_sha:
            repo_name = self._extract_repo_name_from_url(repo_url)
            for file_data in files_data:
                try:
                    # 获取变更前的完整文件内容
                    if file_data['change_type'] != 'added':
                        try:
                            file_data['complete_old_content'] = self.github_client.get_file_content(
                                repo_name, 
                                file_data['old_path'], 
                                ref=commit_sha + "^1"  # 获取提交前的版本
                            )
                        except Exception as e:
                            logger.warning(f"无法获取文件 {file_data['old_path']} 的变更前内容: {str(e)}")
                            file_data['complete_old_content'] = ""
                    
                    # 获取变更后的完整文件内容
                    if file_data['change_type'] != 'deleted':
                        try:
                            file_data['complete_new_content'] = self.github_client.get_file_content(
                                repo_name, 
                                file_data['new_path'], 
                                ref=commit_sha
                            )
                        except Exception as e:
                            logger.warning(f"无法获取文件 {file_data['new_path']} 的变更后内容: {str(e)}")
                            file_data['complete_new_content'] = ""
                except Exception as e:
                    logger.warning(f"处理文件 {file_data.get('new_path', file_data.get('old_path', 'unknown'))} 时出错: {str(e)}")
        
        for file_data in files_data:
            file_path = file_data['new_path']
            # 获取语言类型
            language = self._get_language_by_extension(file_path)
            if not language:
                logger.warning(f"不支持的文件类型: {file_path}")
                continue
                
            # 处理每个diff块
            for diff_block in file_data['diff_blocks']:
                # 检查是否有上下文信息
                if 'context' not in diff_block:
                    continue
                    
                context = diff_block['context']
                context_type = diff_block.get('context_type')
                
                # 提取被修改的代码段
                old_lines = []
                new_lines = []
                for line in diff_block['lines']:
                    if line['type'] == 'delete':
                        old_lines.append(line['content'])
                    elif line['type'] == 'add':
                        new_lines.append(line['content'])
                    elif line['type'] == 'context':
                        old_lines.append(line['content'])
                        new_lines.append(line['content'])
                
                old_code = '\n'.join(old_lines)
                new_code = '\n'.join(new_lines)
                
                # 创建函数信息
                func_info = {
                    'file_path': file_path,
                    'language': language,
                    'context': context,
                    'context_type': context_type,
                    'old_start_line': diff_block['old_start'],
                    'new_start_line': diff_block['new_start'],
                    'old_code': old_code,
                    'new_code': new_code
                }
                
                # 如果能够识别具体的类或函数名，添加相应信息
                if context_type == 'class' and 'class_name' in diff_block:
                    func_info['class_name'] = diff_block['class_name']
                elif context_type == 'function' and 'function_name' in diff_block:
                    func_info['function_name'] = diff_block['function_name']
                
                # 提取变动前和变动后的完整代码内容
                if TS_AVAILABLE and self.parsers.get(language):
                    try:
                        # 处理变动前的代码
                        if old_code:
                            parser = self.parsers[language]
                            # 使用原始文件内容构建语法树，而不是仅使用diff中的代码片段
                            old_tree = parser.parse(bytes(file_data.get('complete_old_content', old_code), 'utf8'))
                            old_root_node = old_tree.root_node
                            
                            # 获取用于解析的文件内容
                            complete_old_content = file_data.get('complete_old_content', old_code)
                            
                            def find_matching_node(node, context_text):
                                """
                                根据上下文文本和行号查找匹配的函数或类节点
                                """
                                function_types = self.FUNCTION_NODE_TYPES.get(language, [])
                                class_types = self.CLASS_NODE_TYPES.get(language, [])
                                
                                # 如果有上下文文本，尝试在完整文件内容中定位行号
                                if context_text:
                                    # 在完整文件内容中查找上下文文本的位置
                                    file_content = complete_old_content
                                    if isinstance(file_content, bytes):
                                        file_content = file_content.decode('utf-8')
                                    
                                    # 尝试查找精确匹配
                                    target_line = None
                                    file_lines = file_content.splitlines()
                                    
                                    # 尝试多种匹配方式
                                    for i, line in enumerate(file_lines):
                                        # 1. 直接匹配
                                        if context_text.strip() in line:
                                            target_line = i
                                            logger.debug(f"通过直接匹配在行 {target_line + 1} 找到上下文文本")
                                            break
                                        
                                        # 2. 忽略空格匹配
                                        if context_text.replace(' ', '').strip() in line.replace(' ', ''):
                                            target_line = i
                                            logger.debug(f"通过忽略空格匹配在行 {target_line + 1} 找到上下文文本")
                                            break
                                    
                                    # 如果找到了匹配行
                                    if target_line is not None:
                                        logger.debug(f"使用上下文文本定位节点，目标行: {target_line + 1}")
                                        
                                        # 查找覆盖指定行号的节点
                                        def find_node_by_line(node):
                                            # 检查节点是否覆盖了目标行
                                            if node.start_point[0] <= target_line and node.end_point[0] >= target_line:
                                                # 检查节点类型是否符合要求
                                                if (context_type == 'function' and node.type in function_types) or \
                                                   (context_type == 'class' and node.type in class_types):
                                                    logger.debug(f"通过行号找到匹配节点，类型: {node.type}, 行范围: {node.start_point[0]}-{node.end_point[0]}")
                                                    return node
                                            
                                            # 递归检查子节点
                                            for child in node.children:
                                                result = find_node_by_line(child)
                                                if result:
                                                    return result
                                            return None
                                        
                                        # 从根节点开始查找
                                        line_match = find_node_by_line(node)
                                        if line_match:
                                            return line_match
                                
                                # 如果通过上下文文本未找到，回退到diff行号
                                if 'old_start' in diff_block:
                                    target_line = diff_block['old_start'] - 1  # 转换为0-indexed
                                    logger.debug(f"使用行号定位节点，目标行: {target_line + 1}")
                                    
                                    # 查找覆盖指定行号的节点
                                    def find_node_by_line(node):
                                        # 检查节点是否覆盖了目标行
                                        if node.start_point[0] <= target_line and node.end_point[0] >= target_line:
                                            # 检查节点类型是否符合要求
                                            if (context_type == 'function' and node.type in function_types) or \
                                               (context_type == 'class' and node.type in class_types):
                                                logger.debug(f"通过行号找到匹配节点，类型: {node.type}, 行范围: {node.start_point[0]}-{node.end_point[0]}")
                                                return node
                                        
                                        # 递归检查子节点
                                        for child in node.children:
                                            result = find_node_by_line(child)
                                            if result:
                                                return result
                                        return None
                                    
                                    # 从根节点开始查找
                                    line_match = find_node_by_line(node)
                                    if line_match:
                                        return line_match
                            
                            old_target_node = None
                            try:
                                old_target_node = find_matching_node(old_root_node, context)
                                if old_target_node:
                                    # 记录节点的字节范围和行范围
                                    logger.debug(f"找到的旧节点信息 - 类型: {old_target_node.type}, 行范围: {old_target_node.start_point[0]+1}-{old_target_node.end_point[0]+1}, 字节范围: {old_target_node.start_byte}-{old_target_node.end_byte}")
                                    
                                    # 基于行号提取代码，而不是字节范围
                                    if isinstance(complete_old_content, bytes):
                                        file_content = complete_old_content.decode('utf-8')
                                    else:
                                        file_content = complete_old_content
                                    
                                    file_lines = file_content.splitlines()
                                    start_line = old_target_node.start_point[0]
                                    end_line = old_target_node.end_point[0]
                                    
                                    # 确保行号在有效范围内
                                    if start_line >= 0 and end_line < len(file_lines):
                                        node_text = '\n'.join(file_lines[start_line:end_line+1])
                                        logger.debug(f"基于行号提取的旧代码长度: {len(node_text)}, 行数: {end_line-start_line+1}")
                                    else:
                                        # 如果行号无效，回退到字节范围
                                        logger.warning(f"行号超出范围，回退到字节范围提取: {start_line}-{end_line}, 文件行数: {len(file_lines)}")
                                        node_text = complete_old_content[old_target_node.start_byte:old_target_node.end_byte]
                                        if isinstance(node_text, bytes):
                                            node_text = node_text.decode('utf-8')
                                    
                                    # 记录提取的代码长度和前后内容
                                    logger.debug(f"提取的旧代码长度: {len(node_text)}, 前20个字符: {node_text[:20].replace('\n', '\\n')}, 后20个字符: {node_text[-20:].replace('\n', '\\n') if len(node_text) > 20 else node_text.replace('\n', '\\n')}")
                                    
                                    if old_code in node_text:
                                        func_info['old_full_code'] = node_text
                                    else:
                                        func_info['old_full_code'] = old_code
                            except Exception as e:
                                logger.error(f"解析旧代码时出错: {str(e)}")
                                # 降级处理：如果无法解析，则使用原始的old_code
                                func_info['old_full_code'] = old_code
                        # 处理变动后的代码
                        if new_code:
                            parser = self.parsers[language]
                            # 使用原始文件内容构建语法树，而不是仅使用diff中的代码片段
                            new_tree = parser.parse(bytes(file_data.get('complete_new_content', new_code), 'utf8'))
                            new_root_node = new_tree.root_node
                            
                            # 获取用于解析的文件内容
                            complete_new_content = file_data.get('complete_new_content', new_code)
                            
                            def find_matching_node(node, context_text):
                                """
                                根据上下文文本和行号查找匹配的函数或类节点
                                """
                                function_types = self.FUNCTION_NODE_TYPES.get(language, [])
                                class_types = self.CLASS_NODE_TYPES.get(language, [])
                                
                                # 如果有上下文文本，尝试在完整文件内容中定位行号
                                if context_text:
                                    # 在完整文件内容中查找上下文文本的位置
                                    file_content = complete_new_content
                                    if isinstance(file_content, bytes):
                                        file_content = file_content.decode('utf-8')
                                    
                                    # 尝试查找精确匹配
                                    target_line = None
                                    file_lines = file_content.splitlines()
                                    
                                    # 尝试多种匹配方式
                                    for i, line in enumerate(file_lines):
                                        # 1. 直接匹配
                                        if context_text.strip() in line:
                                            target_line = i
                                            logger.debug(f"通过直接匹配在行 {target_line + 1} 找到上下文文本")
                                            break
                                        
                                        # 2. 忽略空格匹配
                                        if context_text.replace(' ', '').strip() in line.replace(' ', ''):
                                            target_line = i
                                            logger.debug(f"通过忽略空格匹配在行 {target_line + 1} 找到上下文文本")
                                            break
                                    
                                    # 如果找到了匹配行
                                    if target_line is not None:
                                        logger.debug(f"使用上下文文本定位节点，目标行: {target_line + 1}")
                                        
                                        # 查找覆盖指定行号的节点
                                        def find_node_by_line(node):
                                            # 检查节点是否覆盖了目标行
                                            if node.start_point[0] <= target_line and node.end_point[0] >= target_line:
                                                # 检查节点类型是否符合要求
                                                if (context_type == 'function' and node.type in function_types) or \
                                                   (context_type == 'class' and node.type in class_types):
                                                    logger.debug(f"通过行号找到匹配节点，类型: {node.type}, 行范围: {node.start_point[0]}-{node.end_point[0]}")
                                                    return node
                                            
                                            # 递归检查子节点
                                            for child in node.children:
                                                result = find_node_by_line(child)
                                                if result:
                                                    return result
                                            return None
                                        
                                        # 从根节点开始查找
                                        line_match = find_node_by_line(node)
                                        if line_match:
                                            return line_match
                                
                                # 如果通过上下文文本未找到，回退到diff行号
                                if 'new_start' in diff_block:
                                    target_line = diff_block['old_start'] - 1  # 转换为0-indexed
                                    logger.debug(f"使用行号定位节点，目标行: {target_line + 1}")
                                    
                                    # 查找覆盖指定行号的节点
                                    def find_node_by_line(node):
                                        # 检查节点是否覆盖了目标行
                                        if node.start_point[0] <= target_line and node.end_point[0] >= target_line:
                                            # 检查节点类型是否符合要求
                                            if (context_type == 'function' and node.type in function_types) or \
                                               (context_type == 'class' and node.type in class_types):
                                                logger.debug(f"通过行号找到匹配节点，类型: {node.type}, 行范围: {node.start_point[0]}-{node.end_point[0]}")
                                                return node
                                        
                                        # 递归检查子节点
                                        for child in node.children:
                                            result = find_node_by_line(child)
                                            if result:
                                                return result
                                        return None
                                    
                                    # 从根节点开始查找
                                    line_match = find_node_by_line(node)
                                    if line_match:
                                        return line_match
                            
                            new_target_node = None
                            try:
                                new_target_node = find_matching_node(new_root_node, context)
                                if new_target_node:
                                    # 记录节点的字节范围和行范围
                                    logger.debug(f"找到的新节点信息 - 类型: {new_target_node.type}, 行范围: {new_target_node.start_point[0]+1}-{new_target_node.end_point[0]+1}, 字节范围: {new_target_node.start_byte}-{new_target_node.end_byte}")
                                    
                                    # 基于行号提取代码，而不是字节范围
                                    if isinstance(complete_new_content, bytes):
                                        file_content = complete_new_content.decode('utf-8')
                                    else:
                                        file_content = complete_new_content
                                    
                                    file_lines = file_content.splitlines()
                                    start_line = new_target_node.start_point[0]
                                    end_line = new_target_node.end_point[0]
                                    
                                    # 确保行号在有效范围内
                                    if start_line >= 0 and end_line < len(file_lines):
                                        node_text = '\n'.join(file_lines[start_line:end_line+1])
                                        logger.debug(f"基于行号提取的新代码长度: {len(node_text)}, 行数: {end_line-start_line+1}")
                                    else:
                                        # 如果行号无效，回退到字节范围
                                        logger.warning(f"行号超出范围，回退到字节范围提取: {start_line}-{end_line}, 文件行数: {len(file_lines)}")
                                        node_text = complete_new_content[new_target_node.start_byte:new_target_node.end_byte]
                                        if isinstance(node_text, bytes):
                                            node_text = node_text.decode('utf-8')
                                    
                                    # 记录提取的代码长度和前后内容
                                    logger.debug(f"提取的新代码长度: {len(node_text)}, 前20个字符: {node_text[:20].replace('\n', '\\n')}, 后20个字符: {node_text[-20:].replace('\n', '\\n') if len(node_text) > 20 else node_text.replace('\n', '\\n')}")
                                    
                                    if new_code in node_text:
                                        func_info['new_full_code'] = node_text
                                    else:
                                        func_info['new_full_code'] = new_code
                            except Exception as e:
                                logger.error(f"解析新代码时出错: {str(e)}")
                                # 降级处理：如果无法解析，则使用原始的new_code
                                func_info['new_full_code'] = new_code
                    except Exception as e:
                        logger.error(f"解析代码时出错: {str(e)}")
                
                changed_functions.append(func_info) 

        return changed_functions
    
    def _extract_complete_function_body(self, content: str, start_line: int, end_line: int) -> str:
        """
        从代码内容中提取完整的函数体
        
        Args:
            content: 代码内容
            start_line: 函数开始行 (0-indexed)
            end_line: 函数结束行 (0-indexed)
            
        Returns:
            函数体文本
        """
        if not content:
            return ""
        
        lines = content.splitlines()
        
        # 确保行号在有效范围内
        if start_line < 0:
            start_line = 0
        if end_line >= len(lines):
            end_line = len(lines) - 1
        
        # 提取函数体
        function_body = lines[start_line:end_line+1]
        return '\n'.join(function_body)
    
    def _get_function_body_pair(self, file_old_content: str, file_new_content: str, 
                                func_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取函数体的修改前后版本
        
        Args:
            file_old_content: 修改前的文件内容
            file_new_content: 修改后的文件内容
            func_info: 函数信息，至少包含以下字段:
                - name: 函数名
                - start_line: 开始行
                - end_line: 结束行
                - old_start_line: 旧版本开始行 (如果存在)
                - old_end_line: 旧版本结束行 (如果存在)
                
        Returns:
            扩展的函数信息字典，添加了以下字段:
                - old_body: 修改前的函数体
                - new_body: 修改后的函数体
        """
        result = func_info.copy()
        
        # 获取修改前的函数体
        old_start = func_info.get('old_start_line', func_info['start_line'])
        old_end = func_info.get('old_end_line', func_info['end_line'])
        old_body = self._extract_complete_function_body(file_old_content, old_start, old_end)
        
        # 获取修改后的函数体
        new_body = self._extract_complete_function_body(file_new_content, func_info['start_line'], func_info['end_line'])
        
        result['old_body'] = old_body
        result['new_body'] = new_body
        
        return result

    def process_commit(self, repo_url: str, commit_sha: str, output_format: str = "json") -> Any:
        """
        处理GitHub提交，提取差异信息
        
        Args:
            repo_url: GitHub仓库URL
            commit_sha: 提交SHA
            output_format: 输出格式，"json" 或 "dict"
            
        Returns:
            提交差异信息
        """
        result = self.extract_commit_diff(repo_url, commit_sha)
        
        # 为每个文件中的每个函数添加完整的函数体
        for file_data in result.get('files', []):
            if 'modified_functions' not in file_data:
                continue
            
            old_content = file_data.get('complete_old_content', '')
            new_content = file_data.get('complete_new_content', '')
            
            # 处理函数列表，防止重复输出同一个函数
            unique_functions = {}
            for func in file_data['modified_functions']:
                # 用函数名称 + 类名（如果有）作为唯一标识
                func_key = f"{func.get('class_name', '')}.{func['name']}" if func.get('class_name') else func['name']
                
                # 跳过非函数区域的改动
                if func.get('is_outside_function', False):
                    if func_key not in unique_functions:
                        unique_functions[func_key] = func
                    continue
                
                # 如果是同一个函数的多次改动，合并行号范围
                if func_key in unique_functions:
                    existing_func = unique_functions[func_key]
                    # 更新函数的开始和结束行为最小/最大值
                    existing_func['start_line'] = min(existing_func['start_line'], func['start_line'])
                    existing_func['end_line'] = max(existing_func['end_line'], func['end_line'])
                    if 'old_start_line' in func:
                        existing_func['old_start_line'] = min(
                            existing_func.get('old_start_line', float('inf')), 
                            func['old_start_line']
                        )
                    if 'old_end_line' in func:
                        existing_func['old_end_line'] = max(
                            existing_func.get('old_end_line', 0), 
                            func['old_end_line']
                        )
                else:
                    unique_functions[func_key] = func
            
            # 添加完整的函数体
            file_data['modified_functions_with_body'] = []
            for func_key, func in unique_functions.items():
                # 跳过非函数区域的改动
                if func.get('is_outside_function', False):
                    continue
                
                func_with_body = self._get_function_body_pair(old_content, new_content, func)
                file_data['modified_functions_with_body'].append(func_with_body)
        
        # 根据指定格式返回结果
        if output_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return result

    def fast_process_commit(self, repo_url: str, commit_sha: str, output_format: str = "json") -> Any:
        """
        快速处理GitHub提交，直接从URL获取diff并提取变动函数
        
        此方法比process_commit更快，因为它直接解析diff内容，
        而不需要下载整个文件内容和生成完整的AST
        
        Args:
            repo_url: GitHub仓库URL
            commit_sha: 提交SHA
            output_format: 输出格式，"json" 或 "dict"
            
        Returns:
            包含变动函数信息的结果
        """
        # 直接从GitHub获取diff内容
        diff_text = self.direct_get_commit_diff(repo_url, commit_sha)
        if not diff_text:
            error_msg = f"无法获取提交 {commit_sha} 的diff内容"
            logger.error(error_msg)
            result = {
                "repo_url": repo_url,
                "commit_sha": commit_sha,
                "error": error_msg,
                "changed_functions": []
            }
            
            if output_format == "json":
                return json.dumps(result, ensure_ascii=False, indent=2)
            return result
        
        # 从diff直接提取变动函数
        changed_functions = self.extract_changed_functions_from_diff(diff_text, repo_url, commit_sha)
        
        # 构建结果
        result = {
            "repo_url": repo_url,
            "commit_sha": commit_sha,
            "changed_functions": changed_functions
        }
        
        # 根据指定格式返回结果
        if output_format == "json":
            return json.dumps(result, ensure_ascii=False, indent=2)
        return result

def main():
    """
    命令行入口
    """
    import argparse
    parser = argparse.ArgumentParser(description='从GitHub提交中提取函数级别的差异信息')
    parser.add_argument('repo_url', help='GitHub仓库URL')
    parser.add_argument('commit_sha', help='提交SHA')
    parser.add_argument('--output', choices=['json', 'dict'], default='json', help='输出格式')
    parser.add_argument('--output-file', help='输出文件路径，默认为stdout')
    parser.add_argument('--github-token', help='GitHub API令牌')
    parser.add_argument('--fast', action='store_true', help='使用快速处理模式（直接从URL获取diff）')
    
    args = parser.parse_args()
    
    # 设置GitHub令牌（如果提供）
    if args.github_token:
        os.environ['GITHUB_TOKEN'] = args.github_token
    
    # 创建提取器
    extractor = DiffFunctionExtractor()
    
    try:
        # 处理提交
        if args.fast:
            result = extractor.fast_process_commit(args.repo_url, args.commit_sha, args.output)
        else:
            result = extractor.process_commit(args.repo_url, args.commit_sha, args.output)
        
        # 输出结果
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result)
            
    except Exception as e:
        logger.error(f"处理提交时出错: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
