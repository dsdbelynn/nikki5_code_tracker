from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import aiohttp
import asyncio

@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "0.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://localhost:3000/api/codes"
        
        # 游戏别名映射到API参数
        self.game_alias_map = {
            # 无限暖暖别名
            "暖5": "infinity",
            "无限暖暖": "infinity",
            "无暖": "infinity",
            "无限": "infinity",
            "infinity": "infinity",
            "infinitynikki": "infinity",
            
            # 闪耀暖暖别名
            "暖4": "shining",
            "闪耀暖暖": "shining",
            "闪暖": "shining",
            "闪耀": "shining",
            "shining": "shining",
            "shiningnikki": "shining",
            
            # 恋与深空别名
            "深空": "deepspace",
            "恋与深空": "deepspace",
            "深空之眠": "deepspace",
            "恋深": "deepspace",
            "deepspace": "deepspace"
        }
        
        # 游戏API参数映射到显示名称
        self.game_display_names = {
            "infinity": "无限暖暖",
            "shining": "闪耀暖暖",
            "deepspace": "恋与深空"
        }
    
    async def fetch_codes(self, game_alias):
        """从API获取兑换码数据"""
        game_alias = game_alias.lower()  # 转小写，确保匹配不区分大小写
        
        if game_alias not in self.game_alias_map:
            return f"不支持的游戏类型: {game_alias}，请使用 暖5/暖4/深空 或其他常用名称"
        
        api_game_param = self.game_alias_map[game_alias]
        game_display_name = self.game_display_names[api_game_param]
        url = f"{self.base_url}/{api_game_param}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self.format_codes(game_display_name, data)
                    else:
                        return f"获取{game_display_name}兑换码失败，HTTP状态码: {response.status}"
        except Exception as e:
            logger.error(f"获取兑换码时出错: {str(e)}")
            return f"获取{game_display_name}兑换码时发生错误: {str(e)}"
    
    def format_codes(self, game_name, codes_data):
        """格式化兑换码数据为可读文本"""
        if not codes_data:
            return f"未找到{game_name}的兑换码"
        
        result = [f"【{game_name}】兑换码："]
        
        for code in codes_data:
            code_info = f"- 代码: {code['code']}"
            if 'rewards' in code and code['rewards']:
                code_info += f" (奖励: {code['rewards']})"
            if 'date_added' in code and code['date_added']:
                code_info += f" [添加时间: {code['date_added']}]"
            result.append(code_info)
            
        return "\n".join(result)

    @filter.command("兑换码")
    def echo(self, event: AstrMessageEvent, message: str):
        match message:
            case "暖5" | "无限暖暖" | "无暖" | "无限":
                api_game_param = "infinity"
            case "暖4" | "闪耀暖暖" | "闪暖" | "闪耀":
                api_game_param = "shining"
            case "深空" | "恋与深空" | "深空之眠" | "恋深":
                api_game_param = "deepspace"
            case "help" | "帮助":
                yield event.plain_result("【/code 暖5】查询无限暖暖兑换码\n【/code 暖4】查询闪耀暖暖兑换码\n【/code 深空】查询恋与深空兑换码")
        yield event.plain_result("【/code 暖5】查询无限暖暖兑换码\n【/code 暖4】查询闪耀暖暖兑换码\n【/code 深空】查询恋与深空兑换码")


    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''