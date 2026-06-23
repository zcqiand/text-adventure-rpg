"""text-adventure-rpg: 《Harness 工程：围绕 Claude Code 构建可靠系统》卷一卷二配套案例

包入口。仅暴露版本号；具体功能由各子模块提供，避免在导入时触发
任何 I/O 或副作用——书中第 4 章关于「上下文最小化」的演示物。
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
