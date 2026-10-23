# 多气泡回复（像真人连发几条）

## 问题

单条 SSE 流只对应一个 assistant 消息，模型倾向一次输出长段，不像微信里「连发几条短消息」。

## 方案（业界常用）

1. **System 约束 + 分隔符协议**（本项目采用）  
   在 system 里要求 1～4 条短消息，用单独一行的 `§` 分隔；流式解析分隔符，前端拆成多个气泡。  
   优点：仍是一次 LLM 调用、可流式打字；Character / 部分 IM 机器人同类做法。

2. **结构化 JSON 输出**  
   `response_format: json_object`，如 `{"messages":["a","b"]}`，再逐条入库。  
   优点：解析稳定；缺点：整段 JSON 往往要收完才能展示，首字延迟更大。

3. **编排多轮调用**  
   Planner 决定条数 + 逐条生成。  
   优点：最可控；缺点：慢、贵，不适合轻量聊天。

4. **仅前端启发式切分**  
   按句号/换行拆一条长回复。  
   优点：零改模型；缺点：不可控，易切错。

## 本项目实现

- 后端：`app/services/im_reply.py`（`im_system_prompt`、`iter_bubble_stream`、`split_bubbles`）
- SSE 事件：`delta`、`bubble_break`、`typing_pause`、`done`（含 `assistant_message_ids` 数组）
- 数据库：每条气泡一条 `messages` 行，`role=assistant`
- 前端：`chat.js` 在 `bubble_break` 时追加 assistant 气泡，`typing_pause` 短停

## 调优

- 分隔符、条数上限、停顿毫秒可在 `im_reply.py` / `chat.py` 调整
- 人设里可写「话痨多发几条 / 寡言少条」以强化风格
