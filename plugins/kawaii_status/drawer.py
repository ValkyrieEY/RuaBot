"""绘图模块"""
import platform
import sys
import importlib.util
from io import BytesIO
from pathlib import Path
import cpuinfo
from PIL import Image, ImageDraw, ImageFont

# 动态导入同目录下的模块
_plugin_dir = Path(__file__).parent

def _load_module(name, file_path):
    """动态加载模块"""
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    return None

# 加载依赖模块
model_module = _load_module('kawaii_status_model', _plugin_dir / 'model.py')
utils_module = _load_module('kawaii_status_utils', _plugin_dir / 'utils.py')
data_source_module = _load_module('kawaii_status_data_source', _plugin_dir / 'data_source.py')
color_module = _load_module('kawaii_status_color', _plugin_dir / 'color.py')
path_module = _load_module('kawaii_status_path', _plugin_dir / 'path.py')

# 导入函数和变量
get_status_info = model_module.get_status_info if model_module else None
truncate_string = utils_module.truncate_string if utils_module else None
format_uptime = data_source_module.format_uptime if data_source_module else None
get_bot_uptime = data_source_module.get_bot_uptime if data_source_module else None

# 导入颜色
cpu_color = color_module.cpu_color if color_module else (84, 173, 255, 255)
ram_color = color_module.ram_color if color_module else (255, 179, 204, 255)
disk_color = color_module.disk_color if color_module else (184, 170, 159, 255)
swap_color = color_module.swap_color if color_module else (251, 170, 147, 255)
details_color = color_module.details_color if color_module else (184, 170, 159, 255)
nickname_color = color_module.nickname_color if color_module else (84, 173, 255, 255)
transparent_color = color_module.transparent_color if color_module else (0, 0, 0, 0)

# 导入路径
bg_img_path = path_module.bg_img_path if path_module else _plugin_dir / "resources" / "images" / "background.png"
adlam_font_path = path_module.adlam_font_path if path_module else _plugin_dir / "resources" / "fonts" / "ADLaMDisplay-Regular.ttf"
baotu_font_path = path_module.baotu_font_path if path_module else _plugin_dir / "resources" / "fonts" / "baotu.ttf"
marker_img_path = path_module.marker_img_path if path_module else _plugin_dir / "resources" / "images" / "marker.png"
spicy_font_path = path_module.spicy_font_path if path_module else _plugin_dir / "resources" / "fonts" / "SpicyRice-Regular.ttf"
dingtalk_font_path = path_module.dingtalk_font_path if path_module else _plugin_dir / "resources" / "fonts" / "DingTalk-JinBuTi.ttf"

# 全局变量，在插件加载时初始化
_framework_version = "XQNEXT"
_plugin_version = "0.2.0"
_nickname = "Bot"
_loaded_plugins_count = 0

def set_framework_info(framework_version: str, plugin_version: str, nickname: str, loaded_plugins_count: int):
    """设置框架信息（由插件主文件调用）"""
    global _framework_version, _plugin_version, _nickname, _loaded_plugins_count
    _framework_version = framework_version
    _plugin_version = plugin_version
    _nickname = nickname
    _loaded_plugins_count = loaded_plugins_count

system = platform.uname()

# 字体加载（延迟加载，在第一次调用时加载）
_adlam_fnt = None
_spicy_fnt = None
_baotu_fnt = None
_dingtalk_fnt = None

def _load_fonts():
    """延迟加载字体"""
    global _adlam_fnt, _spicy_fnt, _baotu_fnt, _dingtalk_fnt
    if _adlam_fnt is None:
        _adlam_fnt = ImageFont.truetype(str(adlam_font_path), 36)
        _spicy_fnt = ImageFont.truetype(str(spicy_font_path), 38)
        _baotu_fnt = ImageFont.truetype(str(baotu_font_path), 64)
        _dingtalk_fnt = ImageFont.truetype(str(dingtalk_font_path), 38)


def draw() -> bytes:
    """绘图"""
    if get_status_info is None:
        raise RuntimeError("get_status_info 未加载")
    if truncate_string is None:
        raise RuntimeError("truncate_string 未加载")
    if format_uptime is None or get_bot_uptime is None:
        raise RuntimeError("data_source 模块未加载")
    
    _load_fonts()
    
    with Image.open(bg_img_path).convert("RGBA") as base:
        img = Image.new("RGBA", base.size, (0, 0, 0, 0))
        marker = Image.open(marker_img_path)

        cpu, ram, swap, disk = get_status_info()

        cpu_info = f"{cpu.usage}% - {cpu.freq}Ghz [{cpu.core} core]"
        ram_info = f"{ram.usage} / {ram.total} GB"
        swap_info = f"{swap.usage} / {swap.total} GB"
        disk_info = f"{disk.usage} / {disk.total} GB"

        content = ImageDraw.Draw(img)
        content.text((103, 581), _nickname, font=_baotu_fnt, fill=nickname_color)
        content.text((251, 772), cpu_info, font=_spicy_fnt, fill=cpu_color)
        content.text((251, 927), ram_info, font=_spicy_fnt, fill=ram_color)
        content.text((251, 1081), swap_info, font=_spicy_fnt, fill=swap_color)
        content.text((251, 1235), disk_info, font=_spicy_fnt, fill=disk_color)

        content.arc(
            (103, 724, 217, 838),
            start=-90,
            end=(cpu.usage * 3.6 - 90),
            width=115,
            fill=cpu_color,
        )
        content.arc(
            (103, 878, 217, 992),
            start=-90,
            end=(ram.usage / ram.total * 360 - 90),
            width=115,
            fill=ram_color,
        )
        if swap.total > 0:
            content.arc(
                (103, 1032, 217, 1146),
                start=-90,
                end=(swap.usage / swap.total * 360 - 90),
                width=115,
                fill=swap_color,
            )
        content.arc(
            (103, 1186, 217, 1300),
            start=-90,
            end=(disk.usage / disk.total * 360 - 90),
            width=115,
            fill=disk_color,
        )

        content.ellipse((108, 729, 212, 833), width=105, fill=transparent_color)
        content.ellipse((108, 883, 212, 987), width=105, fill=transparent_color)
        content.ellipse((108, 1037, 212, 1141), width=105, fill=transparent_color)
        content.ellipse((108, 1192, 212, 1295), width=105, fill=transparent_color)

        content.text(
            (352, 1378),
            f"{truncate_string(cpuinfo.get_cpu_info()['brand_raw'])}",
            font=_adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1431),
            f"{truncate_string(system.system + ' ' + system.release)}",
            font=_adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1484),
            f"{_framework_version} x Plugin {_plugin_version}",
            font=_adlam_fnt,
            fill=details_color,
        )
        content.text(
            (352, 1537),
            f"{_loaded_plugins_count} loaded",
            font=_adlam_fnt,
            fill=details_color,
        )
        content.text(
            (957, 1703),
            format_uptime(get_bot_uptime()),
            font=_dingtalk_fnt,
            fill=details_color,
            anchor="ra",
        )

        nickname_length = _baotu_fnt.getlength(_nickname)
        img.paste(marker, (103 + int(nickname_length) + 44, 595), marker)

        out = Image.alpha_composite(base, img)

        byte_io = BytesIO()
        out.save(byte_io, format="png")
        img_bytes = byte_io.getvalue()

        return img_bytes

