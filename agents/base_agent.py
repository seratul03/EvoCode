import os
import re
import logging
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

from evoflow.client import EvoClient

logger = logging.getLogger(__name__)

class BaseAgent:

    def __init__(self, client: EvoClient):
        self.client = client
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        templates_dir = os.path.join(project_root, "templates")
        
        if not os.path.exists(templates_dir):
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")
            
        self.jinja_env = Environment(loader=FileSystemLoader(templates_dir))

    def render_template(self, template_path: str, **kwargs) -> str:
        try:
            template = self.jinja_env.get_template(template_path)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"Failed to render template '{template_path}': {e}")
            raise

    def extract_tag(self, text: str, tag_name: str) -> str:
        if not text:
            return ""
        pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    async def execute_call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"Agent executing call (temperature={temperature})")
        return await self.client.create_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
