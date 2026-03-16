
from modules.base_module import BaseCollector
from typing import Dict, Any
import time

class TestCollector(BaseCollector):
    '''Тестовый коллектор.'''
    
    @property
    def name(self) -> str:
        return 'test_module'
    
    async def collect(self) -> Dict[str, Any]:
        return {
            'message': 'Hello from test module!',
            'timestamp': time.time(),
            'type': 'class-based'
        }
