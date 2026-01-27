"""GitHub Issues Capture Plugin - GitHub Issues 和 Commits 卡片渲染插件

适配自 IssuesCaptureIssuesCapture.py
功能：
- 获取 GitHub issue 数据并渲染为美观卡片
- 获取 GitHub commit 数据并渲染为美观卡片
- 支持指定编号或 latest（最新）
- 不需要指令前缀
"""

import os
import asyncio
import re
import platform
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import base64
import requests
from io import BytesIO
from textwrap import wrap

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class GitHubIssuesCapturePlugin:
    """GitHub Issues Capture 插件"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 实例
            config: 插件配置
        """
        self.api = api
        self.config = config
        self.owner = config.get('owner', 'SRInternet-Studio')
        self.repo = config.get('repo', 'Jianer_QQ_bot')
        self.github_token = config.get('github_token', '') or os.environ.get('GITHUB_TOKEN', '')
        
        # 命令列表（不需要前缀）
        self.commands = {
            'issue': ['issue', 'issues'],
            'commit': ['commit', 'commits'],
            'pr': ['pr', 'pull', 'pullrequest'],
            'search': ['search'],
            'stats': ['stats', 'statistics', '统计']
        }
    
    async def on_load(self):
        """插件加载时调用"""
        self.api.log("info", "=" * 50)
        self.api.log("info", "GitHub Issues Capture 插件开始加载...")
        self.api.log("info", f"仓库: {self.owner}/{self.repo}")
        self.api.log("info", f"GitHub Token: {'已配置' if self.github_token else '未配置（使用公开 API）'}")
        
        # 检查 PIL
        if not PIL_AVAILABLE:
            self.api.log("error", "PIL/Pillow 未安装，请运行: pip install pillow")
        
        self.api.log("info", "GitHub Issues Capture 插件加载完成！")
        self.api.log("info", "=" * 50)
    
    async def on_unload(self):
        """插件卸载时调用"""
        self.api.log("info", "GitHub Issues Capture 插件已卸载")
    
    async def on_event(self, event_name: str, data: Dict[str, Any]):
        """处理事件
        
        Args:
            event_name: 事件名称
            data: 事件数据
        """
        if event_name == "onebot.message":
            await self.handle_message(data)
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件
        
        Args:
            event: OneBot 消息事件
        """
        try:
            # 获取原始消息
            raw_message = event.get('raw_message', '').strip()
            if not raw_message:
                return
            
            # 解析消息
            msg_parts = raw_message.split()
            if len(msg_parts) < 1:
                return
            
            command = msg_parts[0].lower()
            param = msg_parts[1] if len(msg_parts) > 1 else None
            
            message_type = event.get('message_type')  # 'private' or 'group'
            user_id = event.get('user_id')
            group_id = event.get('group_id')
            message_id = event.get('message_id')
            
            self.api.log("debug", f"收到命令: command={command}, param={param}, msg_parts={msg_parts}")
            
            # 处理统计命令（不需要参数，优先检查）
            if command in self.commands['stats']:
                self.api.log("info", "匹配到 stats 命令")
                await self.handle_stats(message_type, user_id, group_id, message_id)
                return
            
            # 处理搜索命令（需要至少 3 个词）
            if command in self.commands['search']:
                if len(msg_parts) >= 3:
                    search_type = msg_parts[1].lower()  # issue/commit/pr
                    search_query = ' '.join(msg_parts[2:])  # 搜索关键词
                    await self.handle_search(message_type, user_id, group_id, message_id, search_type, search_query)
                return
            
            # 其他命令需要至少 2 个词
            if len(msg_parts) < 2:
                return
            
            # 处理 issue 命令
            if command in self.commands['issue']:
                # 检查是否是查看评论
                if len(msg_parts) >= 3 and msg_parts[2].lower() == 'comments':
                    await self.handle_issue_comments(message_type, user_id, group_id, message_id, param)
                else:
                    await self.handle_issue(message_type, user_id, group_id, message_id, param)
                return
            
            # 处理 commit 命令
            if command in self.commands['commit']:
                await self.handle_commit(message_type, user_id, group_id, message_id, param)
                return
            
            # 处理 PR 命令
            if command in self.commands['pr']:
                # 检查是否是查看评论
                if len(msg_parts) >= 3 and msg_parts[2].lower() == 'comments':
                    await self.handle_pr_comments(message_type, user_id, group_id, message_id, param)
                else:
                    await self.handle_pr(message_type, user_id, group_id, message_id, param)
                return
        
        except Exception as e:
            self.api.log("error", f"处理消息时出错: {e}", exc_info=True)
    
    async def handle_issue(self, message_type: str, user_id: int, group_id: Optional[int], 
                           message_id: Optional[int], param: str):
        """处理 issue 命令
        
        Args:
            message_type: 消息类型
            user_id: 用户 ID
            group_id: 群组 ID（如果是群消息）
            message_id: 消息 ID（用于回复）
            param: 参数（issue 编号或 'latest'）
        """
        # 发送等待消息
        wait_msg = "请等待，正在获取 issue 内容……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            # 获取 issue 数据
            if param == "latest":
                issue_data = await self.get_latest_issue_data()
            else:
                issue_data = await self.get_issue_data(param)
            
            if not issue_data:
                raise ValueError("无法获取 issue 数据，仓库可能没有 issue 或配置有误")
            
            # 渲染卡片
            img_bytes = await self.render_issue_card(issue_data)
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 转换为 base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            
            # 构建回复消息
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except ValueError as e:
            # 用户友好的错误消息（如速率限制）
            self.api.log("warning", f"处理 issue 命令失败: {e}")
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 发送错误消息
            error_msg = str(e)
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        except Exception as e:
            self.api.log("error", f"处理 issue 命令失败: {e}", exc_info=True)
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 发送错误消息
            error_msg = f"获取 issue 失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def handle_commit(self, message_type: str, user_id: int, group_id: Optional[int], 
                           message_id: Optional[int], param: str):
        """处理 commit 命令
        
        Args:
            message_type: 消息类型
            user_id: 用户 ID
            group_id: 群组 ID（如果是群消息）
            message_id: 消息 ID（用于回复）
            param: 参数（commit SHA 或 'latest'）
        """
        # 发送等待消息
        wait_msg = "请等待，正在获取 commit 内容……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            # 获取 commit 数据
            if param == "latest":
                commit_data = await self.get_latest_commit_data()
            else:
                commit_data = await self.get_commit_data(param)
            
            if not commit_data:
                raise ValueError("无法获取 commit 数据，仓库可能没有 commit 或配置有误")
            
            # 渲染卡片
            img_bytes = await self.render_commit_card(commit_data)
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 转换为 base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            
            # 构建回复消息
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except ValueError as e:
            # 用户友好的错误消息（如速率限制）
            self.api.log("warning", f"处理 commit 命令失败: {e}")
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 发送错误消息
            error_msg = str(e)
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        except Exception as e:
            self.api.log("error", f"处理 commit 命令失败: {e}", exc_info=True)
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 发送错误消息
            error_msg = f"获取 commit 失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def get_latest_issue_data(self) -> Optional[Dict[str, Any]]:
        """获取最新的 issue 数据（排除 PR）"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            # 获取更多结果以便过滤掉 PR
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues?state=all&sort=created&direction=desc&per_page=30"
            response = requests.get(url, headers=headers, timeout=10)
            
            # 检查速率限制
            if response.status_code == 403:
                rate_limit_info = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            response.raise_for_status()
            
            all_items = response.json()
            if not all_items:
                return None
            
            # 过滤掉 PR（PR 有 pull_request 字段，issue 没有）
            issues = [item for item in all_items if 'pull_request' not in item]
            
            if not issues:
                return None
            
            # 返回最新的 issue 数据
            return issues[0]
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取最新 issue 数据失败: {e}")
            raise
    
    async def get_issue_data(self, issue_number: str) -> Optional[Dict[str, Any]]:
        """获取指定 issue 的数据"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{issue_number}"
            response = requests.get(url, headers=headers, timeout=10)
            
            # 检查速率限制
            if response.status_code == 403:
                rate_limit_info = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            response.raise_for_status()
            data = response.json()
            
            # 检查是否是 PR
            if 'pull_request' in data:
                raise ValueError(f"编号 {issue_number} 是一个 Pull Request，不是 Issue")
            
            return data
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise ValueError(f"Issue #{issue_number} 不存在")
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取 issue 数据失败: {e}")
            raise
    
    async def get_latest_commit_data(self) -> Optional[Dict[str, Any]]:
        """获取最新的 commit 数据"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            # 获取默认分支的最新 commit
            repo_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            repo_response = requests.get(repo_url, headers=headers, timeout=10)
            
            # 检查速率限制
            if repo_response.status_code == 403:
                rate_limit_info = repo_response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in repo_response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            default_branch = repo_data.get('default_branch', 'main')
            
            # 获取默认分支的最新 commit
            commit_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits?sha={default_branch}&per_page=1"
            commit_response = requests.get(commit_url, headers=headers, timeout=10)
            
            # 检查速率限制
            if commit_response.status_code == 403:
                rate_limit_info = commit_response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in commit_response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            commit_response.raise_for_status()
            commit_data = commit_response.json()
            
            if not commit_data:
                return None
            
            return commit_data[0]
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取最新 commit 数据失败: {e}")
            raise
    
    async def get_commit_data(self, sha: str) -> Optional[Dict[str, Any]]:
        """获取指定 commit 的数据"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits/{sha}"
            response = requests.get(url, headers=headers, timeout=10)
            
            # 检查速率限制
            if response.status_code == 403:
                rate_limit_info = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise ValueError(f"Commit {sha[:7]} 不存在")
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取 commit 数据失败: {e}")
            raise
    
    async def get_latest_pr_data(self) -> Optional[Dict[str, Any]]:
        """获取最新的 PR 数据"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?state=all&sort=created&direction=desc&per_page=1"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 403:
                rate_limit_info = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            response.raise_for_status()
            prs = response.json()
            if not prs:
                return None
            return prs[0]
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取最新 PR 数据失败: {e}")
            raise
    
    async def get_pr_data(self, pr_number: str) -> Optional[Dict[str, Any]]:
        """获取指定 PR 的数据"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 403:
                rate_limit_info = response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise ValueError(f"PR #{pr_number} 不存在")
            if e.response and e.response.status_code == 403:
                error_msg = "GitHub API 速率限制已超，请稍后再试"
                if not self.github_token:
                    error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                raise ValueError(error_msg)
            raise
        except Exception as e:
            self.api.log("error", f"获取 PR 数据失败: {e}")
            raise
    
    async def get_issue_comments(self, issue_number: str) -> List[Dict[str, Any]]:
        """获取 Issue 评论"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments?per_page=10"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.api.log("error", f"获取 Issue 评论失败: {e}")
            return []
    
    async def get_pr_comments(self, pr_number: str) -> List[Dict[str, Any]]:
        """获取 PR 评论"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{pr_number}/comments?per_page=10"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.api.log("error", f"获取 PR 评论失败: {e}")
            return []
    
    async def search_issues(self, query: str) -> List[Dict[str, Any]]:
        """搜索 Issues"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            # GitHub 搜索 API
            search_query = f"repo:{self.owner}/{self.repo} {query} type:issue"
            url = f"https://api.github.com/search/issues?q={search_query}&per_page=10"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            self.api.log("error", f"搜索 Issues 失败: {e}")
            return []
    
    async def search_prs(self, query: str) -> List[Dict[str, Any]]:
        """搜索 PRs"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            search_query = f"repo:{self.owner}/{self.repo} {query} type:pr"
            url = f"https://api.github.com/search/issues?q={search_query}&per_page=10"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            self.api.log("error", f"搜索 PRs 失败: {e}")
            return []
    
    async def search_commits(self, query: str) -> List[Dict[str, Any]]:
        """搜索 Commits"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            search_query = f"repo:{self.owner}/{self.repo} {query}"
            url = f"https://api.github.com/search/commits?q={search_query}&per_page=10"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('items', [])
        except Exception as e:
            self.api.log("error", f"搜索 Commits 失败: {e}")
            return []
    
    async def get_repo_stats(self) -> Dict[str, Any]:
        """获取仓库统计信息"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        # 初始化默认值
        stats = {
            'repo': {},
            'issues_count': 0,
            'prs_count': 0,
            'recent_commits': 0,
            'stars': 0,
            'forks': 0,
            'watchers': 0,
            'contributors': 1,  # 默认至少1个（仓库所有者）
        }
        
        try:
            # 获取仓库信息
            repo_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
            repo_response = requests.get(repo_url, headers=headers, timeout=10)
            
            # 检查速率限制
            if repo_response.status_code == 403:
                rate_limit_info = repo_response.headers.get('X-RateLimit-Remaining', '0')
                if rate_limit_info == '0' or 'rate limit' in repo_response.text.lower():
                    error_msg = "GitHub API 速率限制已超，请稍后再试"
                    if not self.github_token:
                        error_msg += "\n提示：配置 GitHub Token 可以提高速率限制（每小时 5000 次）"
                    raise ValueError(error_msg)
            
            repo_response.raise_for_status()
            repo_data = repo_response.json()
            stats['repo'] = repo_data
            stats['stars'] = repo_data.get('stargazers_count', 0)
            stats['forks'] = repo_data.get('forks_count', 0)
            stats['watchers'] = repo_data.get('watchers_count', 0)
            
            # 获取仓库所有者头像
            owner_data = repo_data.get('owner', {})
            stats['avatar_url'] = owner_data.get('avatar_url', '')
            
            # 获取 Issues 统计（使用搜索 API，排除 PR）
            try:
                search_url = f"https://api.github.com/search/issues?q=repo:{self.owner}/{self.repo}+type:issue"
                search_response = requests.get(search_url, headers=headers, timeout=10)
                if search_response.status_code == 200:
                    stats['issues_count'] = search_response.json().get('total_count', 0)
                else:
                    # 如果搜索失败，使用仓库信息中的 open_issues_count（只包含 open 的）
                    stats['issues_count'] = repo_data.get('open_issues_count', 0)
            except Exception as e:
                self.api.log("warning", f"获取 Issues 统计失败: {e}")
                stats['issues_count'] = repo_data.get('open_issues_count', 0)
            
            # 获取 PRs 统计
            try:
                prs_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls?state=all&per_page=1"
                prs_response = requests.get(prs_url, headers=headers, timeout=10)
                if prs_response.status_code == 200:
                    link_header = prs_response.headers.get('Link', '')
                    if 'rel="last"' in link_header:
                        match = re.search(r'page=(\d+)>; rel="last"', link_header)
                        if match:
                            stats['prs_count'] = int(match.group(1))
            except Exception as e:
                self.api.log("warning", f"获取 PRs 统计失败: {e}")
            
            # 获取 Commits 统计（最近30天）
            try:
                since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                commits_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits?since={since_date}&per_page=100"
                commits_response = requests.get(commits_url, headers=headers, timeout=10)
                if commits_response.status_code == 200:
                    recent_commits = commits_response.json()
                    stats['recent_commits'] = len(recent_commits)
            except Exception as e:
                self.api.log("warning", f"获取 Commits 统计失败: {e}")
            
            # 获取 Contributors 统计
            try:
                contributors_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contributors?per_page=1"
                contributors_response = requests.get(contributors_url, headers=headers, timeout=10)
                if contributors_response.status_code == 200:
                    link_header = contributors_response.headers.get('Link', '')
                    if 'rel="last"' in link_header:
                        match = re.search(r'page=(\d+)>; rel="last"', link_header)
                        if match:
                            stats['contributors'] = int(match.group(1))
                    else:
                        # 如果没有分页，说明只有1页，需要获取实际数量
                        contributors_data = contributors_response.json()
                        stats['contributors'] = len(contributors_data) if contributors_data else 1
            except Exception as e:
                self.api.log("warning", f"获取 Contributors 统计失败: {e}")
            
            return stats
        except ValueError:
            raise
        except Exception as e:
            self.api.log("error", f"获取仓库统计失败: {e}", exc_info=True)
            # 即使部分失败，也返回已有的数据
            return stats
    
    def _strip_markdown(self, text: str) -> str:
        """简单去除 Markdown 格式"""
        # 移除代码块
        text = re.sub(r'```[\s\S]*?```', '[代码块]', text)
        # 移除行内代码
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 移除链接
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # 移除粗体/斜体
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        # 移除标题
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        return text.strip()
    
    def _clean_text(self, text: str) -> str:
        """清理文本，移除或替换特殊字符"""
        # 替换可能无法显示的字符
        replacements = {
            '●': '*',
            '·': '|',
            '…': '...',
            '—': '-',
            '–': '-',
            '“': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '《': '<',
            '》': '>',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        # 移除 emoji 和其他特殊 Unicode 字符（保留基本 ASCII 和中文）
        text = re.sub(r'[^\x00-\x7F\u4e00-\u9fff\s]', '', text)
        return text.strip()
    
    def _get_plugin_font_path(self, font_filename: str) -> Optional[str]:
        """获取插件字体路径"""
        plugin_dir = Path(__file__).parent
        font_path = plugin_dir / "fonts" / font_filename
        if font_path.exists():
            return str(font_path)
        return None
    
    def _wrap_text(self, text: str, width: int, font) -> List[str]:
        """文本换行"""
        lines = []
        for paragraph in text.split('\n'):
            if not paragraph.strip():
                lines.append('')
                continue
            words = paragraph.split()
            current_line = ''
            for word in words:
                test_line = current_line + (' ' if current_line else '') + word
                # 估算文本宽度（简单方法）
                if len(test_line) > width:
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                    else:
                        # 单词太长，强制换行
                        lines.append(word)
                        current_line = ''
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)
        return lines
    
    async def render_issue_card(self, issue_data: Dict[str, Any]) -> bytes:
        """渲染 Issue 卡片
        
        Args:
            issue_data: Issue 数据
        
        Returns:
            图片字节
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        # 在线程池中执行（CPU 密集型）
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_issue_card_sync, issue_data)
    
    def _render_issue_card_sync(self, issue_data: Dict[str, Any]) -> bytes:
        """同步渲染 Issue 卡片"""
        # 卡片尺寸
        card_width = 800
        padding = 40
        content_width = card_width - padding * 2
        
        # 颜色
        bg_color = (255, 255, 255)  # 白色背景
        title_color = (36, 41, 46)  # GitHub 深灰
        text_color = (88, 96, 105)  # GitHub 浅灰
        border_color = (225, 228, 232)  # GitHub 边框色
        label_colors = {
            'bug': (215, 58, 73),
            'enhancement': (63, 185, 80),
            'question': (101, 163, 13),
        }
        
        # 创建图片
        img = Image.new('RGB', (card_width, 1200), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 尝试加载字体（优先使用插件字体）
        title_font = None
        body_font = None
        meta_font = None
        
        # 尝试加载插件字体
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        adlam_path = self._get_plugin_font_path("ADLaMDisplay-Regular.ttf")
        
        try:
            if dingtalk_path:
                title_font = ImageFont.truetype(dingtalk_path, 28)
                body_font = ImageFont.truetype(dingtalk_path, 18)
                meta_font = ImageFont.truetype(dingtalk_path, 14)
        except:
            pass
        
        # 如果部分字体加载失败，使用备用字体
        if not title_font and dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 28)
            except:
                pass
        if not body_font and dingtalk_path:
            try:
                body_font = ImageFont.truetype(dingtalk_path, 18)
            except:
                pass
        if not meta_font and dingtalk_path:
            try:
                meta_font = ImageFont.truetype(dingtalk_path, 14)
            except:
                pass
        
        # 如果都失败，使用默认字体
        if not title_font:
            title_font = ImageFont.load_default()
        if not body_font:
            body_font = ImageFont.load_default()
        if not meta_font:
            meta_font = ImageFont.load_default()
        
        y = padding
        
        # 标题
        title = f"#{issue_data.get('number', '?')} {issue_data.get('title', 'Untitled')}"
        title = self._clean_text(title)
        title_lines = self._wrap_text(title, 60, title_font)
        for line in title_lines[:2]:  # 最多两行
            draw.text((padding, y), line, fill=title_color, font=title_font)
            y += 35
        y += 10
        
        # 状态和标签
        state = issue_data.get('state', 'open')
        state_color = (63, 185, 80) if state == 'open' else (130, 149, 159)
        state_text = '* OPEN' if state == 'open' else '* CLOSED'
        draw.text((padding, y), state_text, fill=state_color, font=meta_font)
        
        # 标签
        labels = issue_data.get('labels', [])
        label_x = padding + 100
        for label in labels[:5]:  # 最多显示 5 个标签
            label_name = label.get('name', '')
            label_color = label.get('color', '0366d6')
            # 绘制标签背景
            label_width = len(label_name) * 8 + 10
            draw.rectangle(
                [label_x, y, label_x + label_width, y + 20],
                fill=f"#{label_color}"
            )
            label_name_clean = self._clean_text(label_name)
            draw.text((label_x + 5, y + 2), label_name_clean, fill=(255, 255, 255), font=meta_font)
            label_x += label_width + 10
        y += 30
        
        # 分隔线
        draw.line([(padding, y), (card_width - padding, y)], fill=border_color, width=1)
        y += 20
        
        # 作者和时间
        user = issue_data.get('user', {})
        author = user.get('login', 'unknown')
        created_at = issue_data.get('created_at', '')
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = created_at[:10]
        else:
            time_str = "Unknown"
        
        meta_text = f"@{author} | {time_str}"
        meta_text = self._clean_text(meta_text)
        draw.text((padding, y), meta_text, fill=text_color, font=meta_font)
        y += 30
        
        # 内容
        body = issue_data.get('body', '')
        if body:
            body = self._strip_markdown(body)
            body = self._clean_text(body)
            body_lines = self._wrap_text(body, 70, body_font)
            for line in body_lines[:15]:  # 最多 15 行
                if y > 1000:
                    draw.text((padding, y), "...", fill=text_color, font=body_font)
                    break
                draw.text((padding, y), line, fill=text_color, font=body_font)
                y += 22
        
        # 底部信息
        y = 1150
        repo_text = f"{self.owner}/{self.repo}"
        repo_text = self._clean_text(repo_text)
        draw.text((padding, y), repo_text, fill=text_color, font=meta_font)
        
        # 边框
        draw.rectangle([0, 0, card_width - 1, 1199], outline=border_color, width=2)
        
        # 保存到字节
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def render_commit_card(self, commit_data: Dict[str, Any]) -> bytes:
        """渲染 Commit 卡片
        
        Args:
            commit_data: Commit 数据
        
        Returns:
            图片字节
        """
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        # 在线程池中执行（CPU 密集型）
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_commit_card_sync, commit_data)
    
    def _render_commit_card_sync(self, commit_data: Dict[str, Any]) -> bytes:
        """同步渲染 Commit 卡片"""
        # 卡片尺寸（增加高度以显示 diff）
        card_width = 800
        padding = 40
        content_width = card_width - padding * 2
        
        # 计算所需高度
        files = commit_data.get('files', [])
        diff_lines_count = 0
        for file in files[:5]:  # 最多显示 5 个文件的 diff
            patch = file.get('patch', '')
            if patch:
                diff_lines = patch.split('\n')
                diff_lines_count += min(len(diff_lines), 30)  # 每个文件最多 30 行
        
        # 基础高度 + diff 高度
        base_height = 400
        diff_height = diff_lines_count * 18  # 每行 18px
        card_height = min(base_height + diff_height, 2000)  # 最大 2000px
        
        # 颜色
        bg_color = (255, 255, 255)
        title_color = (36, 41, 46)
        text_color = (88, 96, 105)
        border_color = (225, 228, 232)
        sha_color = (88, 96, 105)
        add_color = (40, 167, 69)  # GitHub 绿色
        del_color = (203, 36, 49)  # GitHub 红色
        diff_bg_add = (240, 255, 244)  # 浅绿背景
        diff_bg_del = (255, 238, 240)  # 浅红背景
        
        # 创建图片
        img = Image.new('RGB', (card_width, card_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 尝试加载字体（优先使用插件字体）
        title_font = None
        body_font = None
        meta_font = None
        code_font = None
        
        # 尝试加载插件字体
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        adlam_path = self._get_plugin_font_path("ADLaMDisplay-Regular.ttf")
        
        try:
            if dingtalk_path:
                title_font = ImageFont.truetype(dingtalk_path, 24)
                body_font = ImageFont.truetype(dingtalk_path, 18)
                meta_font = ImageFont.truetype(dingtalk_path, 14)
            if adlam_path:
                code_font = ImageFont.truetype(adlam_path, 14)
        except:
            pass
        
        # 如果部分字体加载失败，使用备用字体
        if not title_font and dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 24)
            except:
                pass
        if not body_font and dingtalk_path:
            try:
                body_font = ImageFont.truetype(dingtalk_path, 18)
            except:
                pass
        if not meta_font and dingtalk_path:
            try:
                meta_font = ImageFont.truetype(dingtalk_path, 14)
            except:
                pass
        if not code_font and adlam_path:
            try:
                code_font = ImageFont.truetype(adlam_path, 14)
            except:
                pass
        
        # 如果都失败，使用默认字体
        if not title_font:
            title_font = ImageFont.load_default()
        if not body_font:
            body_font = ImageFont.load_default()
        if not meta_font:
            meta_font = ImageFont.load_default()
        if not code_font:
            code_font = ImageFont.load_default()
        
        y = padding
        
        # SHA
        sha = commit_data.get('sha', '')[:7]
        sha_text = f"Commit {sha}"
        sha_text = self._clean_text(sha_text)
        draw.text((padding, y), sha_text, fill=sha_color, font=code_font)
        y += 30
        
        # 提交信息
        commit_info = commit_data.get('commit', {})
        message = commit_info.get('message', 'No message')
        message = self._clean_text(message)
        message_lines = message.split('\n')
        main_message = message_lines[0] if message_lines else 'No message'
        main_message_lines = self._wrap_text(main_message, 60, title_font)
        
        for line in main_message_lines[:2]:
            draw.text((padding, y), line, fill=title_color, font=title_font)
            y += 30
        y += 10
        
        # 作者和时间
        author_info = commit_info.get('author', {})
        author_name = author_info.get('name', 'unknown')
        author_date = author_info.get('date', '')
        if author_date:
            try:
                dt = datetime.strptime(author_date, "%Y-%m-%dT%H:%M:%SZ")
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = author_date[:10]
        else:
            time_str = "Unknown"
        
        meta_text = f"{author_name} | {time_str}"
        meta_text = self._clean_text(meta_text)
        draw.text((padding, y), meta_text, fill=text_color, font=meta_font)
        y += 30
        
        # 分隔线
        draw.line([(padding, y), (card_width - padding, y)], fill=border_color, width=1)
        y += 20
        
        # 统计信息
        stats = commit_data.get('stats', {})
        if stats:
            additions = stats.get('additions', 0)
            deletions = stats.get('deletions', 0)
            total = stats.get('total', 0)
            stats_text = f"+{additions} -{deletions} ({total} lines changed)"
            stats_text = self._clean_text(stats_text)
            draw.text((padding, y), stats_text, fill=text_color, font=body_font)
            y += 30
        
        # 文件列表和 diff（最多显示 5 个文件）
        files = commit_data.get('files', [])
        if files:
            files_label = "Changed files:"
            files_label = self._clean_text(files_label)
            draw.text((padding, y), files_label, fill=title_color, font=body_font)
            y += 25
            
            for file_idx, file in enumerate(files[:5]):  # 最多 5 个文件
                filename = file.get('filename', '')
                status = file.get('status', '')
                additions = file.get('additions', 0)
                deletions = file.get('deletions', 0)
                changes = file.get('changes', 0)
                
                # 文件名和统计
                file_text = f"  {status.upper():3} {filename} (+{additions} -{deletions})"
                file_text = self._clean_text(file_text)
                draw.text((padding, y), file_text[:70], fill=title_color, font=body_font)
                y += 25
                
                # 显示 diff
                patch = file.get('patch', '')
                if patch:
                    diff_lines = patch.split('\n')
                    max_diff_lines = 30  # 每个文件最多显示 30 行
                    
                    for line in diff_lines[:max_diff_lines]:
                        if y > card_height - 50:  # 留出底部空间
                            break
                        
                        line_clean = self._clean_text(line)
                        if not line_clean:
                            y += 15
                            continue
                        
                        # 判断是添加还是删除
                        if line_clean.startswith('+') and not line_clean.startswith('+++'):
                            # 添加的行（绿色）
                            # 绘制背景
                            draw.rectangle(
                                [padding - 5, y - 2, card_width - padding + 5, y + 16],
                                fill=diff_bg_add
                            )
                            # 显示行（去掉 + 号）
                            line_display = line_clean[1:][:75]  # 去掉 +，最多 75 字符
                            draw.text((padding, y), line_display, fill=add_color, font=code_font)
                        elif line_clean.startswith('-') and not line_clean.startswith('---'):
                            # 删除的行（红色）
                            # 绘制背景
                            draw.rectangle(
                                [padding - 5, y - 2, card_width - padding + 5, y + 16],
                                fill=diff_bg_del
                            )
                            # 显示行（去掉 - 号）
                            line_display = line_clean[1:][:75]  # 去掉 -，最多 75 字符
                            draw.text((padding, y), line_display, fill=del_color, font=code_font)
                        elif line_clean.startswith('@@'):
                            # diff 头部（灰色，小字）
                            line_display = line_clean[:70]
                            draw.text((padding, y), line_display, fill=text_color, font=meta_font)
                        else:
                            # 上下文行（普通文本）
                            line_display = line_clean[:75]
                            draw.text((padding, y), line_display, fill=text_color, font=code_font)
                        
                        y += 18
                    
                    # 如果还有更多行，显示提示
                    if len(diff_lines) > max_diff_lines:
                        more_text = f"    ... ({len(diff_lines) - max_diff_lines} more lines)"
                        draw.text((padding, y), more_text, fill=text_color, font=meta_font)
                        y += 20
                    
                    y += 10  # 文件之间的间距
            
            # 如果还有更多文件，显示提示
            if len(files) > 5:
                more_files_text = f"... and {len(files) - 5} more files"
                draw.text((padding, y), more_files_text, fill=text_color, font=meta_font)
                y += 20
        
        # 底部信息
        y = card_height - 30
        repo_text = f"{self.owner}/{self.repo}"
        repo_text = self._clean_text(repo_text)
        draw.text((padding, y), repo_text, fill=text_color, font=meta_font)
        
        # 边框
        draw.rectangle([0, 0, card_width - 1, card_height - 1], outline=border_color, width=2)
        
        # 保存到字节
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def render_pr_card(self, pr_data: Dict[str, Any]) -> bytes:
        """渲染 PR 卡片"""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_pr_card_sync, pr_data)
    
    def _render_pr_card_sync(self, pr_data: Dict[str, Any]) -> bytes:
        """同步渲染 PR 卡片"""
        card_width = 800
        padding = 40
        card_height = 1000
        
        bg_color = (255, 255, 255)
        title_color = (36, 41, 46)
        text_color = (88, 96, 105)
        border_color = (225, 228, 232)
        merged_color = (111, 66, 193)  # 紫色
        open_color = (40, 167, 69)  # 绿色
        closed_color = (203, 36, 49)  # 红色
        
        img = Image.new('RGB', (card_width, card_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 加载字体
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        adlam_path = self._get_plugin_font_path("ADLaMDisplay-Regular.ttf")
        
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        
        if dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 24)
                body_font = ImageFont.truetype(dingtalk_path, 18)
                meta_font = ImageFont.truetype(dingtalk_path, 14)
            except:
                pass
        
        y = padding
        
        # 标题
        title = f"#{pr_data.get('number', '?')} {pr_data.get('title', 'Untitled')}"
        title = self._clean_text(title)
        title_lines = self._wrap_text(title, 60, title_font)
        for line in title_lines[:2]:
            draw.text((padding, y), line, fill=title_color, font=title_font)
            y += 30
        y += 10
        
        # 状态
        state = pr_data.get('state', 'open')
        merged = pr_data.get('merged', False)
        if merged:
            state_text = '* MERGED'
            state_color = merged_color
        elif state == 'open':
            state_text = '* OPEN'
            state_color = open_color
        else:
            state_text = '* CLOSED'
            state_color = closed_color
        
        draw.text((padding, y), state_text, fill=state_color, font=meta_font)
        y += 30
        
        # 作者和时间
        user = pr_data.get('user', {})
        author = user.get('login', 'unknown')
        created_at = pr_data.get('created_at', '')
        if created_at:
            try:
                dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = created_at[:10]
        else:
            time_str = "Unknown"
        
        meta_text = f"@{author} | {time_str}"
        meta_text = self._clean_text(meta_text)
        draw.text((padding, y), meta_text, fill=text_color, font=meta_font)
        y += 30
        
        # 分隔线
        draw.line([(padding, y), (card_width - padding, y)], fill=border_color, width=1)
        y += 20
        
        # PR 信息
        base_branch = pr_data.get('base', {}).get('ref', '')
        head_branch = pr_data.get('head', {}).get('ref', '')
        branch_text = f"{head_branch} -> {base_branch}"
        draw.text((padding, y), branch_text, fill=text_color, font=body_font)
        y += 25
        
        # 统计信息
        additions = pr_data.get('additions', 0)
        deletions = pr_data.get('deletions', 0)
        changed_files = pr_data.get('changed_files', 0)
        stats_text = f"+{additions} -{deletions} ({changed_files} files changed)"
        stats_text = self._clean_text(stats_text)
        draw.text((padding, y), stats_text, fill=text_color, font=body_font)
        y += 30
        
        # 内容预览
        body = pr_data.get('body', '')
        if body:
            body = self._strip_markdown(body)
            body = self._clean_text(body)
            body_lines = self._wrap_text(body, 70, body_font)
            for line in body_lines[:10]:
                if y > 900:
                    draw.text((padding, y), "...", fill=text_color, font=body_font)
                    break
                draw.text((padding, y), line, fill=text_color, font=body_font)
                y += 22
        
        # 底部信息
        y = card_height - 30
        repo_text = f"{self.owner}/{self.repo}"
        repo_text = self._clean_text(repo_text)
        draw.text((padding, y), repo_text, fill=text_color, font=meta_font)
        
        # 边框
        draw.rectangle([0, 0, card_width - 1, card_height - 1], outline=border_color, width=2)
        
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def render_comments_card(self, title: str, comments: List[Dict[str, Any]]) -> bytes:
        """渲染评论卡片"""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_comments_card_sync, title, comments)
    
    def _render_comments_card_sync(self, title: str, comments: List[Dict[str, Any]]) -> bytes:
        """同步渲染评论卡片"""
        card_width = 800
        padding = 40
        base_height = 200
        comment_height = 150  # 每个评论约 150px
        card_height = min(base_height + len(comments) * comment_height, 2000)
        
        bg_color = (255, 255, 255)
        title_color = (36, 41, 46)
        text_color = (88, 96, 105)
        border_color = (225, 228, 232)
        comment_bg = (248, 250, 252)
        
        img = Image.new('RGB', (card_width, card_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        
        if dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 24)
                body_font = ImageFont.truetype(dingtalk_path, 16)
                meta_font = ImageFont.truetype(dingtalk_path, 12)
            except:
                pass
        
        y = padding
        
        # 标题
        title = self._clean_text(title)
        draw.text((padding, y), title, fill=title_color, font=title_font)
        y += 40
        
        # 评论列表
        for comment in comments[:10]:  # 最多 10 条评论
            if y > card_height - 50:
                break
            
            # 评论背景
            draw.rectangle(
                [padding - 5, y - 5, card_width - padding + 5, y + comment_height - 10],
                fill=comment_bg,
                outline=border_color,
                width=1
            )
            
            # 作者和时间
            user = comment.get('user', {})
            author = user.get('login', 'unknown')
            created_at = comment.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = created_at[:10]
            else:
                time_str = "Unknown"
            
            author_text = f"@{author} | {time_str}"
            author_text = self._clean_text(author_text)
            draw.text((padding, y), author_text, fill=text_color, font=meta_font)
            y += 20
            
            # 评论内容
            body = comment.get('body', '')
            if body:
                body = self._strip_markdown(body)
                body = self._clean_text(body)
                body_lines = self._wrap_text(body, 75, body_font)
                for line in body_lines[:6]:  # 最多 6 行
                    if y > card_height - 50:
                        break
                    draw.text((padding, y), line, fill=title_color, font=body_font)
                    y += 18
            
            y += 15
        
        # 边框
        draw.rectangle([0, 0, card_width - 1, card_height - 1], outline=border_color, width=2)
        
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def render_search_results_card(self, search_type: str, query: str, results: List[Dict[str, Any]]) -> bytes:
        """渲染搜索结果卡片"""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_search_results_card_sync, search_type, query, results)
    
    def _render_search_results_card_sync(self, search_type: str, query: str, results: List[Dict[str, Any]]) -> bytes:
        """同步渲染搜索结果卡片"""
        card_width = 800
        padding = 40
        item_height = 80
        card_height = min(200 + len(results) * item_height, 1500)
        
        bg_color = (255, 255, 255)
        title_color = (36, 41, 46)
        text_color = (88, 96, 105)
        border_color = (225, 228, 232)
        
        img = Image.new('RGB', (card_width, card_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        
        if dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 22)
                body_font = ImageFont.truetype(dingtalk_path, 16)
                meta_font = ImageFont.truetype(dingtalk_path, 12)
            except:
                pass
        
        y = padding
        
        # 标题
        title = f"Search {search_type.upper()}: {query}"
        title = self._clean_text(title)
        draw.text((padding, y), title, fill=title_color, font=title_font)
        y += 40
        
        # 结果列表
        for idx, item in enumerate(results[:10], 1):
            if y > card_height - 50:
                break
            
            # 编号和标题
            if search_type == 'commit':
                item_title = item.get('commit', {}).get('message', 'No message')
                item_number = item.get('sha', '')[:7]
            else:
                item_title = item.get('title', 'Untitled')
                item_number = f"#{item.get('number', '?')}"
            
            item_title = self._clean_text(item_title)
            title_line = f"{idx}. {item_number} {item_title[:50]}"
            draw.text((padding, y), title_line, fill=title_color, font=body_font)
            y += 22
            
            # 作者和时间
            if search_type == 'commit':
                author = item.get('commit', {}).get('author', {}).get('name', 'unknown')
                date = item.get('commit', {}).get('author', {}).get('date', '')
            else:
                author = item.get('user', {}).get('login', 'unknown')
                date = item.get('created_at', '')
            
            if date:
                try:
                    dt = datetime.strptime(date[:19], "%Y-%m-%dT%H:%M:%S")
                    time_str = dt.strftime("%Y-%m-%d")
                except:
                    time_str = date[:10]
            else:
                time_str = "Unknown"
            
            meta_text = f"   @{author} | {time_str}"
            meta_text = self._clean_text(meta_text)
            draw.text((padding, y), meta_text, fill=text_color, font=meta_font)
            y += 30
        
        # 边框
        draw.rectangle([0, 0, card_width - 1, card_height - 1], outline=border_color, width=2)
        
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def render_stats_card(self, stats_data: Dict[str, Any]) -> bytes:
        """渲染统计图表卡片"""
        if not PIL_AVAILABLE:
            raise RuntimeError("PIL/Pillow 未安装")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._render_stats_card_sync, stats_data)
    
    def _render_stats_card_sync(self, stats_data: Dict[str, Any]) -> bytes:
        """同步渲染统计图表卡片（GitHub 卡片样式 - 高仿版）"""
        card_width = 800
        padding = 40
        card_height = 480  # 减少高度
        
        # 背景色（浅灰色，类似 GitHub）
        bg_color = (246, 248, 250)
        
        # 使用 RGBA 模式以支持透明头像
        img = Image.new('RGBA', (card_width, card_height), (*bg_color, 255))
        draw = ImageDraw.Draw(img)
        
        # 颜色方案（GitHub 风格）
        owner_color = (88, 96, 105)  # 用户名颜色（浅灰）
        repo_color = (36, 41, 46)    # 仓库名颜色（深灰/黑）
        subtitle_color = (88, 96, 105)
        text_color = (88, 96, 105)
        number_color = (36, 41, 46)  # 数字颜色（深色）
        border_color = (225, 228, 232)
        card_bg = (255, 255, 255)  # 卡片背景（白色）
        
        # 绘制白色卡片背景
        card_padding = 20
        draw.rectangle(
            [card_padding, card_padding, card_width - card_padding, card_height - card_padding],
            fill=card_bg,
            outline=border_color,
            width=1
        )
        
        dingtalk_path = self._get_plugin_font_path("DingTalk-JinBuTi.ttf")
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        number_font = ImageFont.load_default()
        
        if dingtalk_path:
            try:
                title_font = ImageFont.truetype(dingtalk_path, 26)
                body_font = ImageFont.truetype(dingtalk_path, 16)
                meta_font = ImageFont.truetype(dingtalk_path, 13)
                number_font = ImageFont.truetype(dingtalk_path, 20)
            except:
                pass
        
        y = padding + card_padding - 5  # 减少顶部间距
        
        # 标题区域（头像在右侧）
        avatar_size = 75  # 放大头像
        avatar_url = stats_data.get('avatar_url', '')
        avatar_x = card_width - padding - card_padding - avatar_size
        avatar_y = y
        
        # 下载并显示头像（在右侧）
        if avatar_url:
            try:
                import requests
                from io import BytesIO
                avatar_response = requests.get(avatar_url, timeout=5)
                if avatar_response.status_code == 200:
                    avatar_img = Image.open(BytesIO(avatar_response.content))
                    # 转换为圆形头像
                    avatar_img = avatar_img.convert('RGBA')
                    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    
                    # 创建圆形遮罩
                    mask = Image.new('L', (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
                    
                    # 应用遮罩
                    avatar_img.putalpha(mask)
                    
                    # 粘贴头像
                    img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
            except Exception as e:
                self.api.log("debug", f"加载头像失败: {e}")
        
        # 标题文本（左侧，用户名和仓库名分开显示）
        owner_text = f"{self.owner}/"
        owner_text = self._clean_text(owner_text)
        repo_text = self._clean_text(self.repo)
        
        title_x = padding + card_padding
        draw.text((title_x, y + 3), owner_text, fill=owner_color, font=title_font)
        
        # 计算仓库名位置（在用户名后面）
        owner_width = title_font.getlength(owner_text)
        draw.text((title_x + owner_width, y + 3), repo_text, fill=repo_color, font=title_font)
        
        y += 30  # 减少间距
        
        # 描述（如果有）
        repo_data = stats_data.get('repo', {})
        description = repo_data.get('description', '')
        if description:
            description = self._clean_text(description)
            desc_lines = self._wrap_text(description, 70, body_font)
            for line in desc_lines[:2]:  # 最多2行
                draw.text((title_x, y), line, fill=subtitle_color, font=body_font)
                y += 18
            y += 25  # 增加间距，让统计数据往下
        else:
            y += 25  # 增加间距，让统计数据往下
        
        # 统计信息区域（横向排列，带图标）
        stats_y = y
        stats_items = [
            ("Contributors", stats_data.get('contributors', 1), "👥"),
            ("Issues+PRs", stats_data.get('issues_count', 0) + stats_data.get('prs_count', 0), "👁"),
            ("Forks", stats_data.get('forks', 0), "🍴"),
            ("Stars", stats_data.get('stars', 0), "⭐"),
        ]
        
        # 计算每个统计项的宽度
        stats_width = (card_width - (padding + card_padding) * 2) // len(stats_items)
        stats_x = padding + card_padding
        
        for idx, (label, value, icon) in enumerate(stats_items):
            stat_x = stats_x + idx * stats_width
            
            # 数值（大字体，粗体效果）
            value_text = f"{value:,}" if value > 0 else "0"
            value_text = self._clean_text(value_text)
            value_y = stats_y + 3
            draw.text((stat_x + 5, value_y), value_text, fill=number_color, font=number_font)
            
            # 标签（小字体，在数值下方）
            label_text = self._clean_text(label)
            label_y = stats_y + 25
            draw.text((stat_x + 5, label_y), label_text, fill=text_color, font=meta_font)
        
        y = stats_y + 65  # 减少间距
        
        # 语言统计（如果有，显示在卡片底部）
        try:
            languages_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/languages"
            headers = {
                "Accept": "application/vnd.github.v3+json",
            }
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            languages_response = requests.get(languages_url, headers=headers, timeout=10)
            if languages_response.status_code == 200:
                languages = languages_response.json()
                if languages:
                    total_bytes = sum(languages.values())
                    
                    # 语言条（在卡片底部）
                    lang_bar_height = 8  # 更细的语言条，类似参考图片
                    lang_bar_x = padding + card_padding
                    lang_bar_y = card_height - padding - card_padding - 50  # 为 URL 和标签留空间
                    lang_bar_width = card_width - (padding + card_padding) * 2
                    
                    # 语言颜色映射
                    lang_colors = {
                        'Python': (53, 114, 124),
                        'JavaScript': (241, 224, 90),
                        'TypeScript': (49, 120, 198),
                        'Java': (244, 121, 51),
                        'Go': (0, 173, 216),
                        'Rust': (0, 0, 0),
                        'C++': (157, 157, 157),
                        'C': (85, 85, 85),
                        'HTML': (227, 76, 38),
                        'CSS': (21, 114, 182),
                        'Shell': (137, 224, 81),
                        'Other': (136, 136, 136),
                    }
                    
                    current_x = lang_bar_x
                    for lang_name, lang_bytes in languages.items():
                        if total_bytes > 0:
                            lang_percentage = (lang_bytes / total_bytes) * 100
                            lang_width = int((lang_percentage / 100) * lang_bar_width)
                            
                            if lang_width > 0:
                                lang_color = lang_colors.get(lang_name, lang_colors['Other'])
                                draw.rectangle(
                                    [current_x, lang_bar_y, current_x + lang_width, lang_bar_y + lang_bar_height],
                                    fill=lang_color
                                )
                                current_x += lang_width
                    
                    # 语言标签（显示主要语言）
                    lang_label_y = lang_bar_y + lang_bar_height + 8
                    main_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
                    lang_labels = []
                    for lang_name, lang_bytes in main_languages:
                        lang_percentage = (lang_bytes / total_bytes) * 100
                        lang_name_clean = self._clean_text(lang_name)
                        lang_labels.append(f"{lang_name_clean} {lang_percentage:.1f}%")
                    
                    lang_text = " | ".join(lang_labels)
                    lang_text = self._clean_text(lang_text)
                    draw.text((lang_bar_x, lang_label_y), lang_text, fill=text_color, font=meta_font)
        except Exception as e:
            self.api.log("debug", f"获取语言统计失败: {e}")
            pass  # 语言统计失败不影响整体显示
        
        # 底部 GitHub URL
        url_y = card_height - padding - card_padding - 15
        repo_text = f"github.com/{self.owner}/{self.repo}"
        repo_text = self._clean_text(repo_text)
        draw.text((padding + card_padding, url_y), repo_text, fill=text_color, font=meta_font)
        
        # 转换为 RGB 模式（如果之前是 RGBA）
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, bg_color)
            rgb_img.paste(img, mask=img.split()[3])  # 使用 alpha 通道作为遮罩
            img = rgb_img
        
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        return output.getvalue()
    
    async def _compress_image(self, img_bytes: bytes) -> bytes:
        """压缩图片
        
        Args:
            img_bytes: 原始图片字节
        
        Returns:
            压缩后的图片字节
        """
        try:
            from PIL import Image
            from io import BytesIO
            
            # 打开图片
            img = Image.open(BytesIO(img_bytes))
            
            # 如果图片太大，进行压缩
            max_size = (1920, 1080)  # 最大尺寸
            max_file_size = 500 * 1024  # 最大 500KB
            
            # 调整尺寸
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 压缩并保存
            output = BytesIO()
            attempts = 0
            while attempts < 5:
                output.seek(0)
                output.truncate()
                # PNG 不支持 quality 参数，使用 optimize
                img.save(output, format='PNG', optimize=True)
                compressed_size = len(output.getvalue())
                
                if compressed_size <= max_file_size:
                    break
                
                # 如果还是太大，进一步缩小尺寸
                new_size = (int(img.size[0] * 0.9), int(img.size[1] * 0.9))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                attempts += 1
            
            return output.getvalue()
        
        except Exception as e:
            self.api.log("warning", f"图片压缩失败，使用原始图片: {e}")
            # 如果压缩失败，限制大小
            if len(img_bytes) > 500 * 1024:
                self.api.log("error", f"图片太大 ({len(img_bytes)} bytes)，无法发送")
                raise ValueError("图片太大，无法发送")
            return img_bytes
    
    async def handle_pr(self, message_type: str, user_id: int, group_id: Optional[int], 
                       message_id: Optional[int], param: str):
        """处理 PR 命令"""
        wait_msg = "请等待，正在获取 PR 内容……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            # 获取 PR 数据
            if param == "latest":
                pr_data = await self.get_latest_pr_data()
            else:
                pr_data = await self.get_pr_data(param)
            
            if not pr_data:
                raise ValueError("无法获取 PR 数据，仓库可能没有 PR 或配置有误")
            
            # 渲染卡片
            img_bytes = await self.render_pr_card(pr_data)
            
            # 删除等待消息
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            # 转换为 base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            
            # 构建回复消息
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except ValueError as e:
            self.api.log("warning", f"处理 PR 命令失败: {e}")
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = str(e)
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        except Exception as e:
            self.api.log("error", f"处理 PR 命令失败: {e}", exc_info=True)
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = f"获取 PR 失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def handle_issue_comments(self, message_type: str, user_id: int, group_id: Optional[int], 
                                   message_id: Optional[int], param: str):
        """处理 Issue 评论查看"""
        wait_msg = "请等待，正在获取评论……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            issue_number = param if param != "latest" else None
            if not issue_number:
                raise ValueError("查看评论需要指定 issue 编号")
            
            comments = await self.get_issue_comments(issue_number)
            if not comments:
                raise ValueError(f"Issue #{issue_number} 没有评论")
            
            # 渲染评论卡片
            img_bytes = await self.render_comments_card(f"Issue #{issue_number} Comments", comments)
            
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except Exception as e:
            self.api.log("error", f"处理评论查看失败: {e}", exc_info=True)
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = f"获取评论失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def handle_pr_comments(self, message_type: str, user_id: int, group_id: Optional[int], 
                                message_id: Optional[int], param: str):
        """处理 PR 评论查看"""
        wait_msg = "请等待，正在获取评论……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            pr_number = param if param != "latest" else None
            if not pr_number:
                raise ValueError("查看评论需要指定 PR 编号")
            
            comments = await self.get_pr_comments(pr_number)
            if not comments:
                raise ValueError(f"PR #{pr_number} 没有评论")
            
            # 渲染评论卡片
            img_bytes = await self.render_comments_card(f"PR #{pr_number} Comments", comments)
            
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except Exception as e:
            self.api.log("error", f"处理评论查看失败: {e}", exc_info=True)
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = f"获取评论失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def handle_search(self, message_type: str, user_id: int, group_id: Optional[int], 
                           message_id: Optional[int], search_type: str, query: str):
        """处理搜索命令"""
        wait_msg = f"请等待，正在搜索 {search_type}……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            if search_type == 'issue':
                results = await self.search_issues(query)
            elif search_type == 'pr':
                results = await self.search_prs(query)
            elif search_type == 'commit':
                results = await self.search_commits(query)
            else:
                raise ValueError(f"不支持的搜索类型: {search_type}，支持: issue, pr, commit")
            
            if not results:
                raise ValueError(f"未找到匹配的 {search_type}")
            
            # 渲染搜索结果卡片
            img_bytes = await self.render_search_results_card(search_type, query, results)
            
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
        
        except Exception as e:
            self.api.log("error", f"处理搜索失败: {e}", exc_info=True)
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = f"搜索失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    
    async def handle_stats(self, message_type: str, user_id: int, group_id: Optional[int], 
                          message_id: Optional[int]):
        """处理统计命令"""
        self.api.log("info", f"收到统计命令请求: message_type={message_type}, user_id={user_id}")
        
        wait_msg = "请等待，正在生成统计图表……"
        if message_type == 'private':
            wait_result = await self.api.send_private_msg(user_id, wait_msg)
        else:
            wait_result = await self.api.send_group_msg(group_id, wait_msg)
        
        wait_message_id = None
        if wait_result.get('success') and wait_result.get('data'):
            wait_message_id = wait_result['data'].get('message_id')
        
        try:
            self.api.log("info", "开始获取仓库统计...")
            # 获取仓库统计
            stats_data = await self.get_repo_stats()
            self.api.log("info", f"获取到统计数据: {stats_data}")
            
            self.api.log("info", "开始渲染统计图表...")
            # 渲染统计图表
            img_bytes = await self.render_stats_card(stats_data)
            self.api.log("info", f"统计图表渲染完成，大小: {len(img_bytes)} bytes")
            
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_cq = f"[CQ:image,file=base64://{img_base64}]"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{img_cq}" if reply_cq else img_cq
            
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
            
            self.api.log("info", "统计图表发送成功")
        
        except Exception as e:
            self.api.log("error", f"处理统计失败: {e}", exc_info=True)
            if wait_message_id:
                await self.api.delete_msg(wait_message_id)
            error_msg = f"生成统计失败: {str(e)}"
            reply_cq = f"[CQ:reply,id={message_id}]" if message_id else ""
            message = f"{reply_cq}{error_msg}" if reply_cq else error_msg
            if message_type == 'private':
                await self.api.send_private_msg(user_id, message)
            else:
                await self.api.send_group_msg(group_id, message)
    

# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 实例
        config: 插件配置
        
    Returns:
        插件实例
    """
    plugin = GitHubIssuesCapturePlugin(api, config)
    await plugin.on_load()
    return plugin

