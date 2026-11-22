"""Run BlackServ Coder with an existing Garlic 1.21 API server."""
import argparse
import json
import os
from .agent import GarlicAgent
from .tools import Tools

def main():
    parser = argparse.ArgumentParser(description="Local Garlic API coding agent")
    parser.add_argument("prompt", help="Task for the local model")
    parser.add_argument("--workspace", required=True, help="Restricted workspace directory")
    parser.add_argument("--api", default="http://127.0.0.1:8080/v1", help="Garlic OpenAI API base URL")
    parser.add_argument("--steps", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.steps <= 30:
        parser.error("--steps must be between 1 and 30")
    agent = GarlicAgent(args.api, Tools(args.workspace),
                        api_key=os.environ.get("GARLIC_API_KEY"), max_steps=args.steps)
    print(json.dumps(agent.run(args.prompt), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
