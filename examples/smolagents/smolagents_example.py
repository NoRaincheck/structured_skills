"""
Example: Using structured_skills with smolagents

This example demonstrates how to wrap structured_skills tools as smolagents Tools
and use them with a CodeAgent.

Requirements:
    pip install structured_skills[smolagents]

Usage:
    python smolagents_example.py
"""

from pathlib import Path

from structured_skills import SkillRegistry
from structured_skills.smolagents import create_smolagents_tools


def main():
    skill_dir = Path(__file__).parent.parent / "skills"

    registry = SkillRegistry(skill_dir)

    tools = create_smolagents_tools(registry)

    print("Created smolagents tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")

    print("\nTesting list_skills tool:")
    list_skills = next(t for t in tools if t.name == "list_skills")
    result = list_skills.forward()
    print(f"  Result: {result}")

    print("\nTesting load_skill tool:")
    load_skill = next(t for t in tools if t.name == "load_skill")
    result = load_skill.forward(skill_name="example-skill")
    print(f"  Result (first 200 chars): {result[:200]}...")

    print("\nTesting run_skill tool:")
    run_skill = next(t for t in tools if t.name == "run_skill")
    result = run_skill.forward(
        skill_name="example-skill", function_name="greet", args={"name": "World"}
    )
    print(f"  Result: {result}")


if __name__ == "__main__":
    main()
