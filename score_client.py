import asyncio
import os
import json
import sys
from typing import Dict, Any, Optional, List, Union
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)


class ScoreMCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.conversation_history = []
        self.tools = []
        self.openai = OpenAI(
            api_key="*",
            base_url="*"
        )
    

    async def connect_to_server(self, server_script_path: str):
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read_stream, write_stream = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await self.session.initialize()
            logging.info("服务器连接成功初始化")
            response = await self.session.list_tools()
            self.tools = response.tools
            logging.info(f"\n服务器可用工具: {[tool.name for tool in self.tools]}")
            return True
        except Exception as e:
            logging.error(f"连接到服务器时出错: {e}")
            return False
        

    async def process_message(self,query:str) -> str:
        if not self.session:
            logging.error("未连接到服务器")
            return "未连接到服务器"
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        formatted_tools = []
        for tool in self.tools:
            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })

        try:
            logging.info("正在发送请求到chatgpt...")
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversation_history,
                tools=formatted_tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message
            final_text = []

            if hasattr(response_message, "tool_calls") and response_message.tool_calls:
                self.conversation_history.append({
                    "role": "assistant",
                    "content":None,
                    "tool_calls":[
                        {
                            "id": tool_call.id,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            },
                            "type": "function"
                        }
                        for tool_call in response_message.tool_calls
                    ]
                })

                for tool_call in response_message.tool_calls:
                    tool_id = tool_call.id
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    # 调用mcp工具
                    try:
                        result = await self.session.call_tool(
                            name=function_name,
                            arguments=function_args
                        )
                        
                        tool_result = ""
                        if hasattr(result,"isError") and result.isError:
                            tool_result = f"工具{function_name}执行失败: {result.error}"
                            if hasattr(result,"content") and result.content:
                                for content_item in result.content:
                                    if hasattr(content_item,"text") and content_item.text:
                                        tool_result = content_item.text
                                        if "input_value=" in tool_result:
                                            import re
                                            match = re.search(r"input_value=(.*)",tool_result)
                                            if match:
                                                try:
                                                    value_dict = eval(match.group(1))
                                                    if 'result' in value_dict:
                                                        tool_result = value_dict['result']
                                                except:
                                                    pass
                        else:
                            tool_result = result.content[0].text


                        self.conversation_history.append({
                            "role":"tool",
                            "tool_call_id":tool_id,
                            "content":tool_result
                        })

                    except Exception as e:
                        logging.error(f"工具{function_name}执行失败: {e}")
                        tool_result = f"工具{function_name}执行失败: {e}"

                    # final_text.append({tool_result})


                follow_up_response = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=self.conversation_history,
                )

                follow_up_message = follow_up_response.choices[0].message
                self.conversation_history.append({
                    "role":"assistant",
                    "content":follow_up_message.content
                })
                final_text.append(follow_up_message.content)
                

            else:
                self.conversation_history.append({
                    "role":"assistant",
                    "content":response_message.content
                })
                
                final_text.append(response_message.content)

            
            return "\n".join(final_text)
        
        except Exception as e:
            error_msg = f"处理请求时出错: {str(e)}"
            logging.error(error_msg)
            return error_msg



    async def interactive_loop(self):
        """运行交互式查询循环"""
        print("\n成绩查询客户端已启动!")
        print("与李明的成绩查询助手对话，GPT-4o将自动决定何时调用工具")
        print("您可以进行连续对话，系统会保留对话历史")
        print("输入'退出'或'exit'结束程序")

        while True:
            try:
                query = input("\n> ").strip()
                if not query:
                    logging.warning("输入不能为空")
                    continue
                if query.lower() in ["退出","exit","quit"]:
                    logging.info("用户请求退出")
                    break
                result = await self.process_message(query)
                print(f"\n{result}")
            except KeyboardInterrupt:
                logging.info("用户手动终止程序")
                break
            except EOFError:
                logging.info("用户输入结束")
                break
            except Exception as e:
                logging.error(f"发生错误: {e}")
                continue



    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
        if self.exit_stack:
            await self.exit_stack.aclose()
        

async def main():
    client = ScoreMCPClient()
    try:
        if await client.connect_to_server("score_server.py"):
            await client.interactive_loop()
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
                        
                        
