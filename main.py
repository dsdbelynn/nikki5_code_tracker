from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://localhost:3000/api/codes"

        @filter.command("兑换码")
        async def code(self, event: AstrMessageEvent, message: str):
            if message == "帮助":
                yield event.plain_result("/兑换码 暖5|暖4|深空")

            elif message == "暖5": 
                yield event.plain_result("无限暖暖")

            elif message == "暖4": 
                yield event.plain_result("闪耀暖暖")

            elif message == "深空": 
                yield event.plain_result("恋与深空")

            else:
                yield event.plain_result("暂不支持")
                
            yield event.plain_result("笑死")

        
    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''