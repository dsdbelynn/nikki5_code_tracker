from astrbot.api.event import MessageChain
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.filter.permission import PermissionType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import aiohttp
import asyncio
import json
import datetime
import os
import socketio

@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "1.0.8")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        self.event_counter = 0  # 添加事件计数器
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://172.17.0.1:3000/api/codes"
        self.subscribers = set()
        # 获取插件所在目录
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        # 创建数据目录
        data_dir = os.path.join(plugin_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # 设置数据文件路径
        self.data_file = os.path.join(data_dir, "subscribers.json")
        
        # 加载已有订阅者
        self.load_subscribers()

        # 初始化Socket.IO客户端
        self.sio = socketio.AsyncClient()
        self.reconnect_task = None  # 跟踪重连任务
        self.reconnecting = False  # 重连状态标志
        self.setup_socketio()
        asyncio.create_task(self.connect_websocket())
    
    def setup_socketio(self):
        """设置Socket.IO客户端事件处理器"""
        """设置Socket.IO客户端事件处理器"""
        
        @self.sio.event
        async def connect():
            logger.info("已连接到WebSocket服务器")
        
        @self.sio.event
        async def disconnect():
            logger.info("与WebSocket服务器断开连接")
            # 确保重置连接状态
            self.reconnecting = False
            # 延迟重连，给服务器时间完全启动
            if not self.reconnect_task or self.reconnect_task.done():
                self.schedule_reconnect(5)  # 增加到10秒

        
        @self.sio.on('new_code')
        async def on_new_code(data):
            self.event_counter += 1
            logger.info(f"收到第 {self.event_counter} 个WebSocket事件: {data}")
            try:
                # 解析接收到的数据
                game_name = data.get('game_name')
                key = data.get('key')
                reward = data.get('reward')
                time = data.get('time')
                url = data.get('url')

                if not game_name or not key:
                    logger.error(f"收到无效的兑换码数据: {data}")
                    return
                
                logger.info(f"收到新兑换码: {game_name} - {key}")

                game_display_name = self.get_game_display_name(game_name)
                msg2 = key
                msg1 = f"🎮 {game_display_name} 兑换码更新啦！\n兑换码：{key}\n奖励：{reward}\n有效期:{time}\n快上游戏兑换叭！\n源链接:{url}"
                message_chain1 = MessageChain().message(msg1)
                message_chain2 = MessageChain().message(msg2)
                for sub in self.subscribers:
                    await self.context.send_message(sub, message_chain1)
                    import asyncio
                    await asyncio.sleep(1)  # 延时1秒钟，可以根据需要调整时间
                    await self.context.send_message(sub, message_chain2)
                    await asyncio.sleep(1)  # 延时1秒钟，可以根据需要调整时间

                
            except Exception as e:
                logger.error(f"处理新兑换码时出错: {str(e)}")
    
    def get_game_display_name(self, game_code):
        """将游戏代码转换为显示名称"""
        game_names = {
            "infinity": "无限暖暖",
            "shining": "闪耀暖暖",
            "deepspace": "恋与深空"
        }
        return game_names.get(game_code, game_code)
    
    async def connect_websocket(self):
        """连接到WebSocket服务器"""
        # 如果已经在重连，直接返回
        if self.reconnecting:
            return
            
        try:
            self.reconnecting = True
            
            # 强制断开并重置客户端状态
            try:
                if self.sio.connected:
                    await self.sio.disconnect()
                await asyncio.sleep(1)  # 等待完全断开
            except Exception as disconnect_error:
                logger.info(f"断开连接时的错误（可以忽略）: {disconnect_error}")
            
            # 创建新的Socket.IO客户端实例以确保干净的状态
            self.sio = socketio.AsyncClient()
            self.setup_socketio()  # 重新设置事件处理器
            
            # 尝试连接
            await self.sio.connect('http://172.17.0.1:3000')
            logger.info("WebSocket连接成功")
            self.reconnecting = False
        
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            self.reconnecting = False
            self.schedule_reconnect(10)  # 延长重连间隔到10秒

    def schedule_reconnect(self, delay):
        """调度一个新的重连任务，取消任何现有任务"""
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        self.reconnect_task = asyncio.create_task(self.delayed_reconnect(delay))
    
    async def delayed_reconnect(self, delay):
        """延迟后尝试重新连接"""
        try:
            await asyncio.sleep(delay)
            await self.connect_websocket()
        except Exception as e:
            logger.error(f"重连过程中出错: {str(e)}")
            # 如果重连失败，继续尝试（最多重试几次）
            if delay < 60:  # 最大延迟60秒
                self.schedule_reconnect(delay * 2)  # 指数退避

    def load_subscribers(self):
        """从文件加载订阅者列表"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.subscribers = set(json.load(f))

        except Exception as e:
            logger.error(f"加载订阅者数据失败: {str(e)}")

    def save_subscribers(self):
        """保存订阅者列表到文件"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(list(self.subscribers), f)
        except Exception as e:
            logger.error(f"保存订阅者数据失败: {str(e)}")
    
    async def fetch_codes(self, game_type):
        """从API获取兑换码数据"""
        url = f"{self.base_url}/{game_type}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
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
    
    def make_ret(self, json_data):
        """
        解析JSON数据，检查兑换码有效性，返回有效的兑换码列表
        
        参数:
            json_data: API返回的JSON数据
            
        返回:
            有效的兑换码列表或错误消息
        """
        # 如果json_data是字符串，很可能是错误消息
        if isinstance(json_data, str):
            return json_data
        
        valid_keys = []
        current_time = datetime.datetime.now()
        
        # 遍历JSON数据中的每个兑换码
        for code_item in json_data:
            # 检查是否包含必要的字段
            if 'code' in code_item and 'end' in code_item:
                try:
                    end_time_str = code_item['end']
                    end_time = datetime.datetime.strptime(end_time_str, "%Y/%m/%d %H:%M:%S")
                    # 检查兑换码是否仍然有效
                    if current_time < end_time:
                        valid_keys.append(code_item['code'])
                except Exception as e:
                    continue
        
        return valid_keys

    @filter.command("兑换码")
    async def code(self, event: AstrMessageEvent, message: str):
        cmd = self.match_cmd(message)
        ret = ""
        if cmd in ["infinity", "shining", "deepspace"]:
            json = await self.fetch_codes(cmd)
            val = self.make_ret(json)
            if isinstance(val, str):
                ret = val
            else:
                if len(val) > 0:
                    for key in val:
                        yield event.plain_result(key)
                else:
                    yield event.plain_result("暂无兑换码")
                ret = "详细信息请查看 https://code.490816852.xyz"

        elif cmd == "help": 
            ret = "输入【/兑换码 游戏】获取兑换码"

        else:
            ret = "输入【】内的指令【/兑换码 help】获取帮助"

        yield event.plain_result(ret)    
        
    @filter.command("兑换码网站")
    async def code_web(self, event: AstrMessageEvent):
        yield event.plain_result("https://code.490816852.xyz")
    
    @filter.command("订阅兑换码")
    async def sub_code(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        
        # 检查是否已经订阅
        if umo in self.subscribers:
            yield event.plain_result("您已经订阅了兑换码推送，无需重复订阅")
        else:
            # 添加到订阅者集合
            self.subscribers.add(umo)
            self.save_subscribers()
            yield event.plain_result("✅ 订阅成功！当有新的兑换码时，我们将会通知您")
            logger.info(f"新用户订阅了兑换码: {umo}")

    @filter.command("取消订阅兑换码")
    async def desub_code(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        
        # 检查是否已经订阅
        if umo in self.subscribers:
            # 从订阅者集合中移除
            self.subscribers.remove(umo)
            self.save_subscribers()
            yield event.plain_result("✅ 已取消订阅兑换码推送")
            logger.info(f"用户取消了兑换码订阅: {umo}")
        else:
            # 用户未订阅
            yield event.plain_result("您当前没有订阅兑换码推送")

    @filter.command("兑换码订阅状态")
    async def sub_status(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        logger.info(f"用户查询了订阅状态： {umo}")

        if umo in self.subscribers:
            yield event.plain_result("✅ 您当前已订阅兑换码推送")
        else:
            yield event.plain_result("❌ 您当前未订阅兑换码推送")

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("订阅测试")
    async def sub_test(self, event: AstrMessageEvent):
        message_chain = MessageChain().message("订阅广播测试!")
        for sub in self.subscribers:
            await self.context.send_message(sub, message_chain)
            
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("订阅列表查询")
    async def sub_list(self, event: AstrMessageEvent):
        ret = ""
        if len(self.subscribers) > 0:
            for s in self.subscribers:
                ret += s
                ret += "\n"
        else:
            ret = "❌没有订阅用户"
        yield event.plain_result(ret)

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("重载订阅列表")
    async def sub_refresh(self, event: AstrMessageEvent):
        self.load_subscribers()        
        ret = "✅ 刷新成功"
        yield event.plain_result(ret)
        ret = ""
        if len(self.subscribers) > 0:
            for s in self.subscribers:
                ret += s
                ret += "\n"
        else:
            ret = "❌没有订阅用户"
        yield event.plain_result(ret)
        
    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''
        # 取消重连任务
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            
        # 断开WebSocket连接
        if self.sio.connected:
            await self.sio.disconnect()
            logger.info("WebSocket连接已关闭")