from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import aiohttp
import asyncio
import json

@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://127.0.0.1:3000/api/codes"
    
    async def fetch_codes(self, game_type):
        """从API获取兑换码数据"""
        url = f"{self.base_url}/{game_type}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return json.dumps(data)
                    else:
                        return f"获取兑换码失败，HTTP状态码: {response.status}"
        except Exception as e:
            return f"获取兑换码时发生错误: {str(e)}"

    def match_cmd(self, cmd):
        ret = ""
        if cmd in ["暖5", "无限暖暖", "无暖"]:
            ret = "infinity"
        elif cmd in ["暖4", "闪耀暖暖", "闪暖"]:
            ret = "shining"
        elif cmd in ["深空", "恋与深空"]:
            ret = "deepspace"
        elif cmd in ["帮助", "help"]:
            ret = "help"
        else:
            ret = ""
        return ret

    @filter.command("兑换码")
    async def code(self, event: AstrMessageEvent, message: str):
        cmd = self.match_cmd(message)
        ret = ""
        if cmd in ["infinity", "shining", "deepspace"]:
            ret = await self.fetch_codes(cmd)
            
            return

        elif cmd == "help": 
            ret = "输入【/兑换码 游戏】获取兑换码"

        else:
            ret = "输入【】内的指令【/兑换码 help】获取帮助"

        yield event.plain_result(ret)
    @filter.command("test")
    async def test(self, event: AstrMessageEvent):
        from astrbot.api.message_components import Node, Plain, Image, Nodes
        node1 = Node(
            uin = 2790771190,
            name = "木木",
            content=[
                Plain("hi111")
            ]
        )
        node2 = Node(
            uin = 2790771190,
            name = "木木",
            content = [
                Plain("hi222")
            ]
        )
        nodes = [node1, node2]
        yield event.chain_result(nodes)
        
    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''