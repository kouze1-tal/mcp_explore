import asyncio
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import CallToolRequest

mcp = FastMCP("score-query")

SCORE_DATA = {
    "语文": 85,
    "数学": 90,
    "英语": 88,
    "物理": 95,
    "化学": 92,
    "生物": 90,
    "政治": 88,
}
PARENT_DATA = {
    "小明": "大明",
    "小狗": "大狗",
}


@mcp.tool()
async def get_score(subject: str) -> CallToolRequest:
    """
    获取学生的成绩
    """
    if subject in SCORE_DATA:
        return CallToolRequest(
            method="tools/call",  # 固定值 'tools/call'
            params={
                "name": "get_score",
                "arguments": {
                    "result": f"{subject}的成绩是{SCORE_DATA[subject]}"
                }
            }
        )
    else:
       return CallToolRequest(
            method="tools/call",  # 固定值 'tools/call'
            params={
                "name": "get_score",
                "arguments": {
                    "result": f"没有找到{subject}的成绩"
                }
            }
        )
    

@mcp.tool()
async def get_parent(name: str) -> CallToolRequest:
    """
    根据学生的姓名获取家长的姓名
    """
    if name in PARENT_DATA:
        return CallToolRequest(
            method="tools/call",  # 固定值 'tools/call'
            params={
                "name": "get_score",
                "arguments": {
                    "result": f"{name}的父亲是{PARENT_DATA[name]}"
                }
            }
        )
    else:
       return CallToolRequest(
            method="tools/call",  # 固定值 'tools/call'
            params={
                "name": "get_score",
                "arguments": {
                    "result": f"没有找到{name}的父亲"
                }
            }
        )
    

if __name__ == "__main__":
    mcp.run(transport='stdio')


if __name__ == "__main__":
    mcp.run(transport='stdio')


