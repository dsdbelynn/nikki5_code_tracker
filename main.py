from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://localhost:3000/api/codes"

        def match_cmd(cmd):
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
            cmd = match_cmd(message)
            ret = ""
            if message == "infinity":
                ret = "无限暖暖"

            elif message == "shining": 
                ret = "闪耀暖暖"

            elif message == "deepspace": 
                ret = "恋与深空"

            elif message == "help": 
                ret = "输入/兑换码 游戏获取兑换码"

            else:
                ret = "输入【】内的指令【/兑换码 help】获取帮助"
                
            yield event.plain_result(ret)

        
    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''