from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("code")
    async def helloworld(self, event: AstrMessageEvent):
        yield event.plain_result("【/code 暖5】查询无限暖暖兑换码\n【/code 暖4】查询闪耀暖暖兑换码\n【/code 深空】查询恋与深空兑换码") # 发送一条纯文本消息

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
