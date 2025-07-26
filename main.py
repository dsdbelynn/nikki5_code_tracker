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
import time
import hashlib

# 使用Docker挂载的数据目录，确保数据持久化
SUBSCRIBERS_FILE_PATH = "/AstrBot/data/subscribers.json"

# 全局变量：存储插件实例，用于清理旧连接
_plugin_instances = {}

@register("nikki5_code_tracker", "Lynn", "一个普通的兑换码查询插件", "1.0.11")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 生成唯一实例ID
        self.instance_id = hashlib.md5(f"{time.time()}_{id(self)}".encode()).hexdigest()[:8]
        logger.info(f"插件实例 {self.instance_id} 初始化")
        
        # 清理旧实例的连接
        self._cleanup_old_instances()
        
        # 注册当前实例
        _plugin_instances[self.instance_id] = self
        
        self.event_counter = 0  # 添加事件计数器
        self.last_notification_time = {}  # 记录最后通知时间，用于去重
        
        # API基础URL，实际使用时应替换为正确的地址
        self.base_url = "http://172.17.0.1:3000/api/codes"
        self.subscribers = set()
        
        # 使用全局配置的数据文件路径
        self.data_file = SUBSCRIBERS_FILE_PATH
        
        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        # 打印路径信息便于调试
        logger.info(f"订阅文件保存路径: {self.data_file}")
        
        # 加载已有订阅者
        self.load_subscribers()

        # 初始化Socket.IO客户端
        self.sio = None
        self.reconnect_task = None  # 跟踪重连任务
        self.reconnecting = False  # 重连状态标志
        self.is_terminated = False  # 标记是否已终止
        
        # 延迟初始化连接，避免立即连接冲突
        asyncio.create_task(self._delayed_init())
    
    async def _delayed_init(self):
        """延迟初始化WebSocket连接"""
        # 等待一小段时间，确保旧连接被清理
        await asyncio.sleep(2)
        if not self.is_terminated:
            await self.init_websocket()
    
    def _cleanup_old_instances(self):
        """清理旧的插件实例连接"""
        instances_to_remove = []
        for instance_id, instance in _plugin_instances.items():
            if instance != self:
                logger.info(f"清理旧插件实例 {instance_id}")
                try:
                    # 异步清理旧实例
                    asyncio.create_task(instance._force_cleanup())
                    instances_to_remove.append(instance_id)
                except Exception as e:
                    logger.error(f"清理旧实例时出错: {e}")
                    instances_to_remove.append(instance_id)
        
        # 从全局字典中移除已清理的实例
        for instance_id in instances_to_remove:
            _plugin_instances.pop(instance_id, None)
    
    async def _force_cleanup(self):
        """强制清理当前实例的连接"""
        try:
            self.is_terminated = True
            
            # 取消重连任务
            if self.reconnect_task and not self.reconnect_task.done():
                self.reconnect_task.cancel()
                
            # 断开WebSocket连接
            if self.sio and self.sio.connected:
                await self.sio.disconnect()
                logger.info(f"实例 {self.instance_id} WebSocket连接已强制关闭")
                
        except Exception as e:
            logger.error(f"强制清理实例 {self.instance_id} 时出错: {e}")
    
    async def init_websocket(self):
        """初始化WebSocket连接"""
        if self.is_terminated:
            return
            
        self.sio = socketio.AsyncClient()
        self.setup_socketio()
        await self.connect_websocket()
    
    def setup_socketio(self):
        """设置Socket.IO客户端事件处理器"""
        
        @self.sio.event
        async def connect():
            if not self.is_terminated:
                logger.info(f"实例 {self.instance_id} 已连接到WebSocket服务器")
        
        @self.sio.event
        async def disconnect():
            if not self.is_terminated:
                logger.info(f"实例 {self.instance_id} 与WebSocket服务器断开连接")
                # 确保重置连接状态
                self.reconnecting = False
                # 延迟重连，给服务器时间完全启动
                if not self.reconnect_task or self.reconnect_task.done():
                    self.schedule_reconnect(5)

        @self.sio.on('new_code')
        async def on_new_code(data):
            if self.is_terminated:
                return
                
            self.event_counter += 1
            logger.info(f"实例 {self.instance_id} 收到第 {self.event_counter} 个WebSocket事件: {data}")
            
            try:
                # 解析接收到的数据
                game_name = data.get('game_name')
                key = data.get('key')
                reward = data.get('reward')
                time_str = data.get('time')
                url = data.get('url')

                if not game_name or not key:
                    logger.error(f"收到无效的兑换码数据: {data}")
                    return
                
                # 生成通知唯一标识，用于去重
                notification_key = f"{game_name}_{key}_{time_str}"
                current_time = time.time()
                
                # 检查是否是重复通知（10秒内的相同通知）
                if notification_key in self.last_notification_time:
                    if current_time - self.last_notification_time[notification_key] < 10:
                        logger.info(f"忽略重复通知: {notification_key}")
                        return
                
                # 记录通知时间
                self.last_notification_time[notification_key] = current_time
                
                # 清理旧的通知记录（保留最近1小时的记录）
                self._cleanup_old_notifications(current_time)
                
                logger.info(f"实例 {self.instance_id} 处理新兑换码: {game_name} - {key}")

                game_display_name = self.get_game_display_name(game_name)
                msg2 = key
                msg1 = f"🎮 {game_display_name} 兑换码更新啦！\n兑换码：{key}\n奖励：{reward}\n有效期:{time_str}\n快上游戏兑换叭！\n源链接:{url}"
                message_chain1 = MessageChain().message(msg1)
                message_chain2 = MessageChain().message(msg2)
                
                for sub in self.subscribers:
                    if not self.is_terminated:
                        await self.context.send_message(sub, message_chain1)
                        await asyncio.sleep(1)  # 延时1秒钟
                        await self.context.send_message(sub, message_chain2)
                        await asyncio.sleep(1)  # 延时1秒钟
                
            except Exception as e:
                logger.error(f"处理新兑换码时出错: {str(e)}")
    
    def _cleanup_old_notifications(self, current_time):
        """清理旧的通知记录"""
        keys_to_remove = []
        for key, timestamp in self.last_notification_time.items():
            if current_time - timestamp > 3600:  # 清理1小时前的记录
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.last_notification_time[key]
    
    def get_game_display_name(self, game_code):
        """将游戏代码转换为显示名称"""
        game_names = {
            "InfinityNikki": "无限暖暖",
            "ShiningNikki": "闪耀暖暖", 
            "DeepSpace": "恋与深空",
            "infinity": "无限暖暖",
            "shining": "闪耀暖暖",
            "deepspace": "恋与深空"
        }
        return game_names.get(game_code, game_code)
    
    async def connect_websocket(self):
        """连接到WebSocket服务器"""
        if self.is_terminated or self.reconnecting:
            return
            
        try:
            self.reconnecting = True
            
            # 强制断开并重置客户端状态
            try:
                if self.sio and self.sio.connected:
                    await self.sio.disconnect()
                await asyncio.sleep(1)  # 等待完全断开
            except Exception as disconnect_error:
                logger.info(f"断开连接时的错误（可以忽略）: {disconnect_error}")
            
            # 重新初始化客户端
            if not self.is_terminated:
                self.sio = socketio.AsyncClient()
                self.setup_socketio()  # 重新设置事件处理器
                
                # 尝试连接
                await self.sio.connect('http://172.17.0.1:3000')
                logger.info(f"实例 {self.instance_id} WebSocket连接成功")
            
            self.reconnecting = False
        
        except Exception as e:
            logger.error(f"实例 {self.instance_id} WebSocket连接失败: {str(e)}")
            self.reconnecting = False
            if not self.is_terminated:
                self.schedule_reconnect(10)  # 延长重连间隔到10秒

    def schedule_reconnect(self, delay):
        """调度一个新的重连任务，取消任何现有任务"""
        if self.is_terminated:
            return
            
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        self.reconnect_task = asyncio.create_task(self.delayed_reconnect(delay))
    
    async def delayed_reconnect(self, delay):
        """延迟后尝试重新连接"""
        try:
            await asyncio.sleep(delay)
            if not self.is_terminated:
                await self.connect_websocket()
        except Exception as e:
            logger.error(f"重连过程中出错: {str(e)}")
            # 如果重连失败，继续尝试（最多重试几次）
            if delay < 60 and not self.is_terminated:  # 最大延迟60秒
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
        message_chain = MessageChain().message(f"订阅广播测试! (实例 {self.instance_id})")
        for sub in self.subscribers:
            await self.context.send_message(sub, message_chain)
            
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("订阅列表查询")
    async def sub_list(self, event: AstrMessageEvent):
        ret = f"当前实例: {self.instance_id}\n"
        if len(self.subscribers) > 0:
            for s in self.subscribers:
                ret += s
                ret += "\n"
        else:
            ret += "❌没有订阅用户"
        yield event.plain_result(ret)

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("重载订阅列表")
    async def sub_refresh(self, event: AstrMessageEvent):
        self.load_subscribers()        
        ret = "✅ 刷新成功"
        yield event.plain_result(ret)
        ret = f"当前实例: {self.instance_id}\n"
        if len(self.subscribers) > 0:
            for s in self.subscribers:
                ret += s
                ret += "\n"
        else:
            ret += "❌没有订阅用户"
        yield event.plain_result(ret)
    
    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("连接状态")
    async def connection_status(self, event: AstrMessageEvent):
        status = f"实例ID: {self.instance_id}\n"
        status += f"WebSocket连接: {'已连接' if self.sio and self.sio.connected else '未连接'}\n"
        status += f"重连中: {'是' if self.reconnecting else '否'}\n"
        status += f"已终止: {'是' if self.is_terminated else '否'}\n"
        status += f"收到事件数: {self.event_counter}\n"
        status += f"活跃实例数: {len(_plugin_instances)}"
        yield event.plain_result(status)
        
    async def terminate(self):
        '''当插件被卸载/停用时会调用'''
        logger.info(f"正在终止插件实例 {self.instance_id}")
        
        # 标记为已终止
        self.is_terminated = True
        
        # 从全局实例字典中移除
        _plugin_instances.pop(self.instance_id, None)
        
        # 取消重连任务
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            
        # 断开WebSocket连接
        if self.sio and self.sio.connected:
            try:
                await self.sio.disconnect()
                logger.info(f"实例 {self.instance_id} WebSocket连接已关闭")
            except Exception as e:
                logger.error(f"关闭WebSocket连接时出错: {e}")
