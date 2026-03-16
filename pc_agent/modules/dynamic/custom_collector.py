
from modules.base_module import BaseCollector
from typing import Dict, Any
import time

class CustomCollector(BaseCollector):
    '''Пример класса-коллектора.'''
    
    @property
    def name(self) -> str:
        return 'custom'
    
    async def collect(self) -> Dict[str, Any]:
        return {
            'message': 'Hello from CustomCollector!',
            'timestamp': time.time(),
            'type': 'class-based'
        }
