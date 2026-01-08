# -*- coding: utf-8 -*-
"""
数科数字员工助手 Streamlit 主应用入口。

此文件定义了应用的核心UI布局和交互逻辑:
- 左侧边栏: 用于展示和管理模型的"数字记忆"。
- 主区域: 分为对话区和工具/RAG面板。
  - 对话区: 处理用户输入、显示聊天历史和流式响应。
  - 工具/RAG面板: 展示后台工具调用和信息检索的过程与结果。

通过 session_state 管理整个应用的会话状态。
"""

import uuid

import streamlit as st

from src.memory.preset import PRESET_MEMORIES
from src.services.agent_sync import initialize_agent, run_agent_streaming

# --- Page Configuration ---
st.set_page_config(
    page_title="数科数字员工助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .st-expander-header {
        font-size: 1.1rem;
        font-weight: bold;
    }
    .stButton>button {
        border-radius: 8px;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


# --- Session State Initialization ---
def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "learned_memories" not in st.session_state:
        st.session_state.learned_memories = []
    if "retrieved_memories" not in st.session_state:
        st.session_state.retrieved_memories = []
    if "tool_calls" not in st.session_state:
        st.session_state.tool_calls = []
    if "rag_results" not in st.session_state:
        st.session_state.rag_results = []
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    # Session history for conversation list
    if "sessions" not in st.session_state:
        st.session_state.sessions = []  # List of {id, title, timestamp}
    # Current bookings for display
    if "current_bookings" not in st.session_state:
        st.session_state.current_bookings = []


# --- Sidebar (Memory Panel) ---
def render_sidebar():
    """Render the memory panel in sidebar."""
    with st.sidebar:
        st.title("🧠 数字记忆")

        # Session management section
        st.subheader("💬 会话管理")
        st.caption(f"当前会话: {st.session_state.thread_id[:8]}...")

        # New conversation button
        if st.button("➕ 新建对话", use_container_width=True):
            # Save current session to history if it has messages
            if st.session_state.messages:
                first_msg = st.session_state.messages[0].get("content", "新对话")
                title = first_msg[:20] + "..." if len(first_msg) > 20 else first_msg
                current_id = st.session_state.thread_id

                # Check if session already exists (update) or is new (append)
                existing_idx = None
                for idx, s in enumerate(st.session_state.sessions):
                    if s["id"] == current_id:
                        existing_idx = idx
                        break

                session_data = {
                    "id": current_id,
                    "title": title,
                    "messages": st.session_state.messages.copy(),
                }

                if existing_idx is not None:
                    st.session_state.sessions[existing_idx] = session_data
                else:
                    st.session_state.sessions.append(session_data)

            # Clear for new session (but keep learned_memories!)
            st.session_state.messages = []
            st.session_state.retrieved_memories = []
            st.session_state.tool_calls = []
            st.session_state.rag_results = []
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()

        # Show session history
        if st.session_state.sessions:
            st.caption("历史会话:")
            # Use enumerate index for unique keys
            display_sessions = list(reversed(st.session_state.sessions[-5:]))
            for i, session in enumerate(display_sessions):
                if st.button(
                    f"📝 {session['title']}",
                    key=f"session_{i}_{session['id'][:8]}",
                    use_container_width=True,
                ):
                    # Restore session
                    st.session_state.thread_id = session["id"]
                    st.session_state.messages = session["messages"].copy()
                    st.session_state.retrieved_memories = []
                    st.session_state.tool_calls = []
                    st.session_state.rag_results = []
                    st.rerun()

        st.divider()

        # Preset memories (built-in)
        st.subheader("📌 内置记忆")
        for memory in PRESET_MEMORIES:
            mem_type = memory.type.value
            emoji = {
                "preference": "⭐",
                "interest": "💡",
                "terminology": "📝",
                "fact": "📋",
            }.get(mem_type, "📌")
            st.info(f"{emoji} [{mem_type}] {memory.content}")

        st.divider()

        # Learned memories
        st.subheader("🎓 习得记忆")
        if st.session_state.learned_memories:
            for mem in st.session_state.learned_memories:
                content = mem.get("content", "")
                mem_type = mem.get("type", "preference")
                st.success(f"⭐ [{mem_type}] {content}")
        else:
            st.caption("暂无习得记忆...")

        st.divider()

        # Current bookings section
        st.subheader("📅 我的预订")
        if st.session_state.current_bookings:
            for booking in st.session_state.current_bookings:
                room = booking.get("room", "N/A")
                date = booking.get("date", "N/A")
                time = booking.get("time", "N/A")
                with st.container(border=True):
                    st.markdown(f"**{room}**")
                    st.caption(f"📆 {date} ⏰ {time}")
        else:
            st.caption("暂无预订...")

        st.divider()

        # Real-time retrieved memories
        st.subheader("🔍 实时检索")
        if st.session_state.retrieved_memories:
            st.write("根据当前对话检索到相关记忆:")
            for mem in st.session_state.retrieved_memories:
                content = mem.get("content", "")
                mem_type = mem.get("type", "unknown")
                score = mem.get("score", 0.0)

                with st.container():
                    st.success(f"**[{mem_type}]** {content}")
                    st.progress(min(score, 1.0), text=f"相关度: {score:.2f}")
        else:
            st.caption("暂无实时检索...")


# --- Right Panel (Tools & RAG) ---
def render_right_panel():
    """Render the tool/RAG panel."""
    st.header("⚙️ 智能面板")

    # Tool calls section
    with st.expander("🛠️ 工具调用", expanded=bool(st.session_state.tool_calls)):
        if st.session_state.tool_calls:
            for tool in reversed(st.session_state.tool_calls):
                name = tool.get("name", "unknown")
                status = tool.get("status", "completed")
                tool_input = tool.get("input", {})
                output = tool.get("output")

                status_icon = "✅" if status == "completed" else "⏳"
                st.markdown(f"**{status_icon} {name}**")

                # Show input
                if tool_input:
                    with st.expander("输入参数", expanded=False):
                        st.json(tool_input)

                # Show output
                if output:
                    with st.container(border=True):
                        if isinstance(output, dict):
                            if "success" in output:
                                if output.get("success"):
                                    st.success(output.get("message", "成功"))
                                else:
                                    st.warning(output.get("message", "失败"))
                            elif "results" in output:
                                # Search results
                                st.markdown("**搜索结果:**")
                                for i, result in enumerate(output.get("results", [])[:3]):
                                    st.markdown(f"**{i+1}. {result.get('title', '')}**")
                                    st.caption(result.get("snippet", "")[:150] + "...")
                                    if result.get("url"):
                                        st.caption(f"🔗 {result.get('url')}")
                            elif "room" in output:
                                # Calendar booking result
                                st.markdown(f"**会议室:** {output.get('room', 'N/A')}")
                                st.markdown(f"**日期:** {output.get('date', 'N/A')}")
                                st.markdown(f"**时间:** {output.get('time', 'N/A')}")
                            elif "bookings" in output:
                                # Query result
                                bookings = output.get("bookings", [])
                                if bookings:
                                    for b in bookings:
                                        date_time = f"{b.get('date')} {b.get('time')}"
                                        st.markdown(f"- **{b.get('room')}** @ {date_time}")
                                else:
                                    st.info("暂无预订记录")
                            else:
                                st.json(output)
                        else:
                            st.write(str(output))
                st.divider()
        else:
            st.caption("暂无工具调用记录")

    # RAG results section
    with st.expander("📚 RAG 检索", expanded=bool(st.session_state.rag_results)):
        if st.session_state.rag_results:
            for i, result in enumerate(st.session_state.rag_results):
                content = result.get("content", "")
                mem_type = result.get("type", "unknown")
                score = result.get("score", 0.0)

                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**#{i+1} [{mem_type}]**")
                        st.write(content)
                    with col2:
                        st.metric("Reranker", f"{score:.2f}")
        else:
            st.caption("暂无RAG检索结果")


# --- Chat Area ---
def render_chat_area():
    """Render the main chat area."""
    # Starter buttons (only show when no messages)
    if not st.session_state.messages:
        st.markdown("### 👋 你好！我是数科数字员工助手")
        st.markdown("我可以帮你预订会议室、搜索新闻资讯，并且会记住你的偏好。")
        st.divider()

        st.subheader("快捷指令 ✨")
        cols = st.columns(4)
        starters = [
            ("📅 预订会议室", "帮我订个会议室"),
            ("🔍 查询会议室", "查询我预订的会议室"),
            ("📰 今日新闻", "今天有什么值得看的新闻？"),
            ("🤖 AI 资讯", "帮我搜索最新的 AI 行业资讯"),
        ]
        for i, (label, prompt) in enumerate(starters):
            with cols[i]:
                if st.button(label, use_container_width=True, key=f"starter_{i}"):
                    st.session_state.pending_prompt = prompt
                    st.rerun()

    # Display chat history
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        avatar = "🧑‍💻" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(content)


def process_message(prompt: str):
    """Process a user message and get agent response."""
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Clear previous results
    st.session_state.tool_calls = []
    st.session_state.rag_results = []
    st.session_state.retrieved_memories = []

    # Display user message
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # Get agent response with streaming
    with st.chat_message("assistant", avatar="🤖"):
        response_placeholder = st.empty()
        full_response = ""

        with st.spinner("思考中..."):
            # Pass chat history (exclude the message we just added)
            chat_history = st.session_state.messages[:-1]
            stream = run_agent_streaming(
                prompt,
                thread_id=st.session_state.thread_id,
                chat_history=chat_history,
            )
            for event_type, data in stream:
                if event_type == "memories":
                    st.session_state.retrieved_memories = [
                        {
                            "content": m.get("content", ""),
                            "type": m.get("type", "unknown"),
                            "score": m.get("rerank_score", 0.0),
                        }
                        for m in data
                    ]
                    st.session_state.rag_results = st.session_state.retrieved_memories

                elif event_type == "token":
                    full_response += data
                    response_placeholder.markdown(full_response + "▌")

                elif event_type == "tool_start":
                    st.session_state.tool_calls.append({
                        "name": data.get("name", "unknown"),
                        "input": data.get("input", {}),
                        "status": "running",
                        "output": None,
                    })
                    st.toast(f"🔧 正在调用工具: {data.get('name', '')}")

                elif event_type == "tool_end":
                    tool_output = data.get("output")
                    tool_name = data.get("name", "")
                    if st.session_state.tool_calls:
                        st.session_state.tool_calls[-1]["status"] = "completed"
                        st.session_state.tool_calls[-1]["output"] = tool_output
                    st.toast(f"✅ 工具调用完成: {tool_name}")

                    # Capture booking results for display
                    if tool_name == "book_meeting_room" and isinstance(tool_output, dict):
                        if tool_output.get("success"):
                            st.session_state.current_bookings.append({
                                "room": tool_output.get("room"),
                                "date": tool_output.get("date"),
                                "time": tool_output.get("time"),
                            })
                            st.toast("📅 会议已预订！")

                elif event_type == "memory_saved":
                    # Add to learned memories and show toast
                    new_memory = {
                        "content": data.get("content", ""),
                        "type": data.get("type", "preference"),
                    }
                    st.session_state.learned_memories.append(new_memory)
                    st.toast("✅ 已记住您的偏好")

                elif event_type == "done":
                    full_response = data

                elif event_type == "error":
                    full_response = f"❌ 发生错误: {data}"

        response_placeholder.markdown(full_response)

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": full_response})


def main():
    """Main application entry point."""
    init_session_state()

    # Initialize agent on first run
    if not st.session_state.initialized:
        with st.spinner("正在初始化数字员工助手..."):
            try:
                initialize_agent()
                st.session_state.initialized = True
            except Exception as e:
                st.error(f"初始化失败: {e}")
                st.stop()

    # Render sidebar (memory panel)
    render_sidebar()

    # Main content area with two columns
    col_chat, col_panel = st.columns([6, 4])

    with col_chat:
        st.title("🤖 数科数字员工助手")
        render_chat_area()

        # Handle pending prompt from starter buttons
        if st.session_state.pending_prompt:
            prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None
            process_message(prompt)
            st.rerun()

        # Chat input
        if prompt := st.chat_input("请输入您的问题..."):
            process_message(prompt)
            st.rerun()

    with col_panel:
        render_right_panel()


if __name__ == "__main__":
    main()
