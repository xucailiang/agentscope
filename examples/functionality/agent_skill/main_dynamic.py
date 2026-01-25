# -*- coding: utf-8 -*-
"""Example demonstrating dynamic skill loading with directory monitoring."""
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import (
    Toolkit,
    execute_shell_command,
    execute_python_code,
    view_text_file,
)


async def main() -> None:
    """Demonstrate dynamic skill loading with directory monitoring."""
    toolkit = Toolkit()

    # Register basic tools
    toolkit.register_tool_function(execute_shell_command)
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(view_text_file)

    # Monitor a directory for skills - skills will be discovered automatically
    # Any subdirectory containing SKILL.md will be registered as a skill
    print("\033[1;33m=== Monitoring Skills Directory ===\033[0m")
    toolkit.monitor_agent_skills("./skill")

    # Show discovered skills
    print(f"\033[1;32mDiscovered {len(toolkit.skills)} skills:\033[0m")
    for skill_name, skill_info in toolkit.skills.items():
        print(f"  - {skill_name}: {skill_info['description']}")
        print(f"    Source: {skill_info['source']}, Dir: {skill_info['dir']}")
    print()

    # Create agent with monitored skills
    agent = ReActAgent(
        name="Friday",
        sys_prompt=(
            "You are a helpful assistant named Friday.\n\n"
            "# IMPORTANT\n"
            "- Don't make any assumptions. All your knowledge must "
            "come from your equipped skills.\n"
            "- When asked about your skills, list them clearly.\n"
        ),
        model=DashScopeChatModel(
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            model_name="qwen3-max",
            enable_thinking=False,
            stream=True,
        ),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    # Show agent's system prompt with skills
    print("\033[1;32m=== Agent System Prompt ===\033[0m")
    print(agent.sys_prompt)
    print()

    # Test 1: Ask about available skills
    print("\033[1;33m=== Test 1: What skills do you have? ===\033[0m")
    await agent(Msg("user", "What skills do you have?", "user"))
    print()

    # Test 2: Use a specific skill
    print(
        "\033[1;33m=== Test 2: How to create tool functions in "
        "AgentScope? ===\033[0m",
    )
    await agent(
        Msg(
            "user",
            (
                "How to create custom tool functions for agents in "
                "AgentScope?"
            ),
            "user",
        ),
    )
    print()

    # Demonstrate manual refresh
    print("\033[1;33m=== Refreshing Skills (Manual) ===\033[0m")
    stats = toolkit.refresh_monitored_skills(force=False)
    print(
        f"Refresh stats: Added={stats['added']}, "
        f"Modified={stats['modified']}, Removed={stats['removed']}",
    )
    print()

    # Show how to remove monitored directory
    print("\033[1;33m=== Removing Monitored Directory ===\033[0m")
    print("Note: This would remove all auto-discovered skills")
    print("Command: toolkit.remove_monitored_directory('./skill')")
    # Uncomment to actually remove:
    # toolkit.remove_monitored_directory("./skill")
    # print(f"Remaining skills: {len(toolkit.skills)}")


if __name__ == "__main__":
    asyncio.run(main())
