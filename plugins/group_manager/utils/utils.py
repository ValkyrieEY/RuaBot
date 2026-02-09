"""工具函数集合"""

import re
from typing import Dict, Any, List, Optional, Tuple


def parse_at(message: List[Dict]) -> List[int]:
    """从消息段中解析所有@的QQ号
    
    Args:
        message: 消息段列表
    
    Returns:
        QQ号列表
    """
    qq_list = []
    if isinstance(message, list):
        for seg in message:
            if isinstance(seg, dict) and seg.get('type') == 'at':
                qq = seg.get('data', {}).get('qq')
                if qq and qq != 'all':
                    try:
                        qq_list.append(int(qq))
                    except (ValueError, TypeError):
                        pass
    return qq_list


def extract_number_from_text(text: str) -> Optional[int]:
    """从文本中提取数字（用于解析+QQ号）
    
    Args:
        text: 文本内容
    
    Returns:
        提取的数字，如果没有则返回None
    """
    match = re.search(r'\d+', text)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def parse_command_with_separator(text: str, separator: str) -> Tuple[str, ...]:
    """解析带分隔符的命令
    
    Args:
        text: 命令文本
        separator: 分隔符（如#或+）
    
    Returns:
        分割后的元组
    """
    parts = text.split(separator)
    return tuple(part.strip() for part in parts)


def format_time(seconds: int) -> str:
    """格式化时间（秒转为可读格式）
    
    Args:
        seconds: 秒数
    
    Returns:
        格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours > 0:
            return f"{days}天{hours}小时"
        return f"{days}天"


def parse_time_string(time_str: str) -> Optional[int]:
    """解析时间字符串为秒数
    
    支持格式：
    - 纯数字：默认为分钟
    - 带单位：10秒、5分钟、2小时、1天
    
    Args:
        time_str: 时间字符串
    
    Returns:
        秒数，如果解析失败返回None
    """
    time_str = time_str.strip()
    
    # 尝试匹配数字+单位
    match = re.match(r'(\d+)\s*(秒|分|分钟|时|小时|天)', time_str)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if unit == '秒':
            return num
        elif unit in ['分', '分钟']:
            return num * 60
        elif unit in ['时', '小时']:
            return num * 3600
        elif unit == '天':
            return num * 86400
    
    # 纯数字，默认为分钟
    if time_str.isdigit():
        return int(time_str) * 60
    
    return None


def check_fuzzy_match(text: str, pattern: str) -> bool:
    """模糊匹配检查
    
    Args:
        text: 要检查的文本
        pattern: 匹配模式
    
    Returns:
        是否匹配
    """
    return pattern in text


def check_exact_match(text: str, pattern: str) -> bool:
    """精准匹配检查
    
    Args:
        text: 要检查的文本
        pattern: 匹配模式
    
    Returns:
        是否匹配
    """
    return text == pattern


def has_cq_code(message: str, cq_type: str) -> bool:
    """检查消息中是否包含特定类型的CQ码
    
    Args:
        message: 消息文本
        cq_type: CQ码类型（如image、voice等）
    
    Returns:
        是否包含
    """
    pattern = rf'\[CQ:{cq_type}[^\]]*\]'
    return bool(re.search(pattern, message))


def extract_cq_params(message: str, cq_type: str) -> List[Dict[str, str]]:
    """提取消息中指定类型的CQ码参数
    
    Args:
        message: 消息文本
        cq_type: CQ码类型
    
    Returns:
        参数字典列表
    """
    pattern = rf'\[CQ:{cq_type}((?:,[^,\]]+=[^,\]]+)*)\]'
    matches = re.finditer(pattern, message)
    
    results = []
    for match in matches:
        params_str = match.group(1)
        params = {}
        if params_str:
            for param in params_str.split(','):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.strip()] = value.strip()
        results.append(params)
    
    return results


def contains_phone_number(text: str) -> bool:
    """检查文本中是否包含手机号码
    
    Args:
        text: 文本内容
    
    Returns:
        是否包含手机号
    """
    # 匹配11位手机号
    pattern = r'1[3-9]\d{9}'
    return bool(re.search(pattern, text))


def contains_url(text: str) -> bool:
    """检查文本中是否包含链接
    
    Args:
        text: 文本内容
    
    Returns:
        是否包含链接
    """
    # 简单的URL匹配
    pattern = r'https?://[^\s]+'
    return bool(re.search(pattern, text))


def contains_qr_code(message_segments: List[Dict]) -> bool:
    """检查消息中是否包含二维码
    
    注意：这个需要配合图片识别，这里只是检查是否有图片
    实际使用时可能需要调用图片识别API
    
    Args:
        message_segments: 消息段列表
    
    Returns:
        是否可能包含二维码
    """
    # 检查是否有图片
    for seg in message_segments:
        if isinstance(seg, dict) and seg.get('type') == 'image':
            return True
    return False


def build_at_message(qq: int, text: str = "") -> str:
    """构建@消息
    
    Args:
        qq: QQ号
        text: 附加文本
    
    Returns:
        CQ码格式的@消息
    """
    at_code = f"[CQ:at,qq={qq}]"
    if text:
        return f"{at_code} {text}"
    return at_code


def split_list_by_separator(text: str, separator: str = '|') -> List[str]:
    """按分隔符分割列表
    
    Args:
        text: 文本
        separator: 分隔符
    
    Returns:
        分割后的列表
    """
    return [item.strip() for item in text.split(separator) if item.strip()]

