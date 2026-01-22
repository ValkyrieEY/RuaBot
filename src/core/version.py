import tomllib
from pathlib import Path
from typing import Optional

# 缓存版本号，避免重复读取
_version: Optional[str] = None


def get_version() -> str:

    global _version
    
    if _version is not None:
        return _version
    
    try:
        # 获取项目根目录
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        
        # 读取 config.toml
        config_path = project_root / "config.toml"
        
        if config_path.exists():
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
                # 从 [app] 读取版本号
                if "app" in data and "version" in data["app"]:
                    _version = data["app"]["version"]
                else:
                    _version = "0.0.2"
        else:
            # 如果文件不存在，使用默认值
            _version = "0.0.2"
    except Exception as e:
        # 读取失败时使用默认值
        import warnings
        warnings.warn(f"Failed to read version from config.toml: {e}, using default")
        _version = "0.0.2"
    
    return _version


def reset_version_cache():
    """重置版本号缓存（用于测试或重新加载）"""
    global _version
    _version = None


# 模块级别的版本号（方便导入）
__version__ = get_version()

