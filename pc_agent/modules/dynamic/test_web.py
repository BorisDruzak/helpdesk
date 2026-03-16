from modules.base_module import BaseCollector
import time

class TestWebCollector(BaseCollector):
    @property
    def name(self) -> str:
        return 'test_web'
    
    async def collect(self):
        return {'message': 'Hello from web!', 'timestamp': time.time()}